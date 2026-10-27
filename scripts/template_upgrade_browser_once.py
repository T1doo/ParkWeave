"""Default closed browser + read-only real HTTP relay; never fallback to Node."""
from scripts.template_upgrade_http_once import main

if __name__=='__main__':raise SystemExit(main(mode='BROWSER'))
