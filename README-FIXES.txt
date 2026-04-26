Changes made:
- Lowered default template matching confidence from 0.8 to 0.72.
- Added last_start_error attribute to OnmyojiBot to surface start failures.
- start_scanning now sets last_start_error when it cannot start (missing templates, game window issues).
- GUI now shows a warning dialog explaining why start failed.
- Added requirements.txt listing external Python dependencies.
- main.py will now show a friendly message if imports fail and advise installing requirements.

Next steps for you:
- Run: pip install -r requirements.txt
- Start the app: python main.py
- If templates still don't match, open the game at the target resolution (config target_window_w/h), or re-capture templates into templates/realm_raid etc.
