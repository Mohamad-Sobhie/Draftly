# Installing Draftly on a Mac (with Claude Code)

This guide is for installing Draftly on someone else's Mac that already has **Claude Code** (the desktop app or the terminal version) signed in. It takes about 10 minutes.

You don't need to type any commands yourself: Claude Code on that Mac can do the whole install. Copy the prompt in Step 2 and paste it in.

---

## Step 1: Open Claude Code in a starting folder

1. Open the **Claude** desktop app and go to the **Code** tab (or open Terminal and type `claude`).
2. Pick a folder to start in, for example **Documents**. Draftly will be created inside it as a new folder called `my-thesis`.
3. If Claude Code asks "Do you trust this folder?", say **yes**.

## Step 2: Paste this prompt into Claude Code

Copy everything in the box and paste it as one message:

```text
Please install Draftly, a thesis-assistant template, on this Mac. Do it step by step and tell me what you're doing in plain words.

1. Check that these exist, and install anything missing:
   - Homebrew (https://brew.sh). If it's missing, tell me the exact install command to run myself, because it asks for my Mac password.
   - git (`git --version`; if missing, `xcode-select --install` or `brew install git`).
   - Python 3.10 or newer (`python3 --version`; if too old or missing, `brew install python`).
2. Install the optional PDF tools: `brew install poppler tesseract ocrmypdf`. If one fails, carry on and tell me.
3. In the current folder, run:
   git clone https://github.com/Mohamad-Sobhie/Draftly.git my-thesis
4. Run the setup script: `bash my-thesis/scripts/setup.sh`
   It creates a Python environment, installs packages and runs a self-test. Show me a short summary of the result: did the self-test pass?
5. If anything failed, fix it and run the setup script again until the self-test passes.
6. When it's done, tell me the full path of the my-thesis folder and remind me to open THAT folder in Claude Code next.
```

Claude will ask for permission before running some commands. Approve them. If it says Homebrew must be installed by you, run the command it gives you in **Terminal** (it will ask for the Mac password; typing it shows nothing on screen, that's normal), then tell Claude "done".

## Step 3: Open the new thesis folder

1. Start a **new** Claude Code session and choose the **`my-thesis`** folder as its folder (not the starting folder from Step 1).
   - Desktop app: new session, then pick the folder `my-thesis`.
   - Terminal: `cd ~/Documents/my-thesis` then `claude`.
2. When asked "Do you trust this folder?", say **yes**. This matters: Draftly's pre-approved permissions only work in a trusted folder, otherwise the student gets a permission prompt for everything.

## Step 4: First run (do this together with the student)

1. Type **`menu`**.
2. Claude sees there's no thesis brief yet and asks the setup questions (field, university, title, research questions, method, citation style, deadline, word limit, AI-use rules, outline). Let the student answer in their own words.
3. Add a first source: drag 2 or 3 PDFs into the chat and say **"add these"**.
4. Say **"open my library"**. A library page opens in the browser. Bookmark it; the student just refreshes it after changes.

That's it. From now on the student opens the `my-thesis` folder in Claude Code and talks normally. Typing **`menu`** always shows what Draftly can do.

---

## Updating Draftly later

Open the `my-thesis` folder in Claude Code and say:

```text
Update Draftly: run `git pull` in this folder, then `bash scripts/setup.sh`, and tell me if the self-test passed.
```

The student's brief, library, notes and drafts are never touched by an update.

## If something goes wrong

| Problem | Fix |
|---|---|
| "command not found: brew" | Homebrew isn't installed. Install it from https://brew.sh (paste its one-line command into Terminal), then ask Claude to continue. |
| "Python 3.10 or newer is required" | Ask Claude: "install Python with brew and re-run the setup". |
| A pop-up asks to install "command line developer tools" | Click **Install**, wait for it to finish, then tell Claude to continue. |
| Scanned PDFs come out empty | The OCR tools are missing. Ask Claude: "install tesseract and ocrmypdf with brew". |
| Claude asks permission for every little thing | The folder isn't trusted, or the wrong folder is open. Reopen the `my-thesis` folder itself and accept "trust this folder". |
| `git clone` says the folder already exists | A `my-thesis` folder is already there. Ask Claude to use a different name, e.g. `my-thesis-2`. |
