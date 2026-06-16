# npm PATH Limitation

`npm test` could not be executed in this PowerShell environment because `npm` is not available on PATH:

```text
npm : The term 'npm' is not recognized as the name of a cmdlet, function, script file, or operable program.
```

The app-local verifier was still run without package-manager mutation by invoking the same script directly through the bundled Node runtime:

```powershell
& 'C:\Users\John\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' apps\l1gov-desktop-client\scripts\verify-fixture.mjs
```

Result:

```text
slice012 desktop real UAT surface verified
```
