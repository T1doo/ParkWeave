"""Fixed command/PI ABI and creation source contracts, no native API doubles."""
import ast
import ctypes as C
from pathlib import Path
import unittest

from . import restricted_initdb_candidate as n
from .initdb_pipe_candidate import _pipe_name


class RestrictedInitdbSourceChecks(unittest.TestCase):
    def test_process_information_x64_and_real_memory_fields(self):
        self.assertEqual(C.sizeof(n.ProcessInformation), 24)
        self.assertEqual(n.ProcessInformation.pid.offset, 16)
        self.assertEqual(n.ProcessInformation.thread_id.offset, 20)
        info = n.ProcessInformation()
        info.pid, info.thread_id = 101, 102
        self.assertEqual(C.c_uint32.from_buffer(info, 16).value, 101)
        self.assertEqual(C.c_uint32.from_buffer(info, 20).value, 102)

    def test_fixed_initdb_arguments_never_use_old_plaintext_file(self):
        name = _pipe_name('12345678-1234-4234-8234-123456789abc', 'a'*32)
        args = n._arguments(r'C:\private\data\postgresql', name)
        self.assertEqual(args, ('-D', r'C:\private\data\postgresql', '-U', 'postgres',
            '--pwfile', name, '--auth-local=scram-sha-256', '--auth-host=scram-sha-256',
            '--encoding=UTF8', '--locale=C'))
        for data, pipe in ((r'C:\private\data', r'C:\private\secrets\postgres-bootstrap.password'),
                           (r'\relative\data', name), (r'C:\private\data', name+'\0x')):
            with self.assertRaises(n.ProcessRefused): n._arguments(data, pipe)

    def test_creation_source_has_post_callback_freshcheck_and_fixed_native_parameters(self):
        tree = ast.parse(Path(n.__file__).read_text())
        cls = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == '_RestrictedInitdbBackend')
        methods = {x.name:x for x in cls.body if isinstance(x, ast.FunctionDef)}
        calls = [x for x in ast.walk(methods['_native_create']) if isinstance(x, ast.Call)]
        creation = next(x for x in calls if isinstance(x.func, ast.Attribute) and x.func.attr == '_create_as_user')
        registration = next(x for x in calls if isinstance(x.func, ast.Name) and x.func.id == 'register')
        fresh = [x.lineno for x in calls if isinstance(x.func, ast.Attribute) and x.func.attr == '_fresh'
                 and x.lineno < creation.lineno]
        self.assertGreater(max(fresh), registration.lineno)
        self.assertEqual(ast.unparse(creation.args[0]), 'self.owner._derived')
        self.assertEqual([creation.args[i].value for i in (3, 4, 5)], [None, None, True])
        flags = creation.args[6]
        self.assertTrue(all(isinstance(x, (ast.BinOp, ast.Constant, ast.BitOr)) for x in ast.walk(flags)))
        self.assertEqual(eval(compile(ast.Expression(flags), '<fixed-flags>', 'eval'), {'__builtins__': {}}), 0x80404)
        attrs = {x.attr for x in ast.walk(tree) if isinstance(x, ast.Attribute)}
        self.assertFalse(attrs & {'ResumeThread', 'ConnectNamedPipe', 'WriteFile', 'SetTokenInformation'})
        preflight = methods['preflight']
        gate = next(x for x in ast.walk(preflight) if isinstance(x, ast.Call)
                    and isinstance(x.func, ast.Attribute) and x.func.attr == 'require_for_cluster')
        accepted = next(x for x in preflight.body if isinstance(x, ast.Assign)
                        and ast.unparse(x.targets[0]) == 'self._preflight_command')
        self.assertLess(gate.lineno, accepted.lineno)

    def test_factories_remain_closed_and_pipe_claim_is_exact_group(self):
        self.assertFalse(n._RestrictedInitdbBackend.launch_ready)
        self.assertFalse(n._RestrictedInitdbBackend.native_acceptance)
        with self.assertRaisesRegex(n.ProcessRefused, 'NOT_ACCEPTED'): n.native_restricted_initdb()
        tree = ast.parse(Path(n.__file__).read_text())
        core = next(x for x in ast.walk(tree) if isinstance(x, ast.FunctionDef) and x.name == '_native_create')
        claim = next(x for x in ast.walk(core) if isinstance(x, ast.Assign)
                     and ast.unparse(x.targets[0]) == 'self.server._claimed_group')
        self.assertEqual(ast.unparse(claim.value), 'group')
        register = next(x for x in ast.walk(core) if isinstance(x, ast.Call)
                        and isinstance(x.func, ast.Name) and x.func.id == 'register')
        self.assertLess(claim.lineno, register.lineno)
        job_owned = next(x for x in ast.walk(core) if isinstance(x, ast.Assign)
                         and ast.unparse(x.targets[0]) == "r['job']")
        self.assertEqual(ast.unparse(job_owned.value), 'job')
        checked = next(x for x in ast.walk(core) if isinstance(x, ast.Call)
                       and isinstance(x.func, ast.Attribute) and x.func.attr == '_native_result'
                       and len(x.args) == 3 and isinstance(x.args[2], ast.Constant)
                       and x.args[2].value == 'CreateJobObjectW')
        self.assertLess(checked.lineno, job_owned.lineno)
        self.assertLess(job_owned.lineno, register.lineno)


if __name__ == '__main__': unittest.main()
