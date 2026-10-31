# Run SimplyDoc Unified in VS Code

1. Clone this repository or extract `SimplyDoc-Unified.zip`.
2. In VS Code choose **File → Open Folder** and open the project folder containing `backend`, `frontend-react` and `start.ps1`.
3. Copy `.env.example` to `.env` if `.env` does not already exist.
4. Put your Groq key after `GROQ_API_KEY=`. Keep `GROQ_MODEL=openai/gpt-oss-20b` if it is available to your account. Leave `AUTH_PROVIDER=local` for shared email/password login.
5. Use **Terminal → New Terminal**.

## PowerShell terminal

```powershell
.\start.ps1
```

If PowerShell blocks scripts, run this one-command alternative for this process only:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
```

The script creates the virtual environment, installs dependencies, builds the frontend, generates a JWT secret if needed, and starts port **8002**. It does not overwrite an existing `.env` or your Groq key.

## Start with F5 on Windows

After the first setup finishes, stop the terminal server with **Ctrl+C**. With the Microsoft Python and Python Debugger extensions installed, select **Run and Debug → Run SimplyDoc (port 8002)** and press **F5**. The included `.vscode/launch.json` uses the project's `.venv` and `.env`, and displays server output in the Debug Console. Press **Shift+F5** to stop. Keep VS Code open while using the app. Rebuild the frontend with `npm run build` from `frontend-react` after changing frontend code.

## Git Bash terminal

```bash
bash start.sh
```

Or run the steps manually:

```bash
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r backend/requirements.lock.txt
cd frontend-react
npm ci
npm run build
cd ..
./.venv/Scripts/python.exe -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8002
```

Open **http://127.0.0.1:8002**, create an account, choose a workspace, and upload a document. Keep the terminal running. Use Ctrl+C to stop.

After analysis finishes, open the document and choose **Chat with document**. Type your question and press Enter or click **Send**. Replies include source references; click one to check the wording and choose **Back to document chat** to continue. Chat also works for resumes and employment documents.

For resume matching choose **Career & employment → Resume / CV + job matching** before uploading. After analysis, open **Resume profile** or **Job match**.

For scans, set `TESSERACT_CMD` to your Tesseract executable if the app cannot find it automatically. Run the executable with `--list-langs` and confirm `hin` and `eng`. Restart after changing `.env`. See `docs/OCR.md` for details. Do not rely on an R: drive that may not be connected.

If port 8002 is occupied, stop the old process that you started, or run `./start.ps1 -Port 8003` and add `http://127.0.0.1:8003` to `ALLOWED_ORIGINS` in `.env`.

The old app at port 8001 can remain separate. Its accounts and uploaded documents are not copied into this release.
