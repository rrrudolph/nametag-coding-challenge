# Demo walkthrough (two colored windows on one machine is enough)

## One-time setup

```powershell
terraform -chdir=infra apply -auto-approve
python scripts/bootstrap_installs.py
pip install -r requirements.txt
```

## Live demo

```powershell
python scripts/demo.py updater --install a
python scripts/demo.py updater --install b
```

Publish v1, wait for both updaters, open apps:

```powershell
python scripts/publish_release.py --version 1.0.0 --color "#1B4F72"
python scripts/demo.py app --install a
python scripts/demo.py app --install b
```

Publish v2 — both apps relaunch themselves into the new version (window closes and reopens running v2's actual code, new color):

```powershell
python scripts/publish_release.py --version 2.0.0 --color "#0E6655"
```

Pin only **a** back to v1 — a's app relaunches back into v1, b stays on v2:

```powershell
python scripts/pin_client.py --install a --version 1.0.0
```

Clear when done:

```powershell
python scripts/pin_client.py --install a --clear
```
