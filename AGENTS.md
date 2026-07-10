# OAS-K Development Rules

- Do not build, rebuild, package, or export any OAS-K executable unless the
  user explicitly requests an EXE build in the current conversation.
- This prohibition includes running PyInstaller, editing build output for the
  purpose of producing an EXE, or replacing files under `dist/`.
- Code changes, tests, compilation checks, and source-level GUI runs do not
  authorize an EXE build.
