"""One original, untraced Doctor call after targeted command qualification."""
from doctor_stages_once import main


if __name__ == '__main__':
    raise SystemExit(main(branch='refs/heads/dev/windows-doctor-joinpath-20261020', trace=False))
