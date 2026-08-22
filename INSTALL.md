# Installing Folio
The Folio releases allow you to use the writerdeck software on your computer. It allows you to create markdown files (.md) and export them in portable document format (.pdf) formatted according to the Chicago or Modern Language Association's style manuals.

## Which file do I download?
**Windows:** `Folio_0.1.0_x64-setup.exe`

**Mac:** there are two, and you need the one that matches your machine.
Click the Apple menu (top left hand corner) → **About This Mac** and look at the line for **Chip** or **Processor**:

| It says | Download |
| --- | --- |
| Apple M1, M2, M3, M4… | `Folio_0.1.0_aarch64.dmg` |
| Intel | `Folio_0.1.0_x64.dmg` |

## Mac
Open the `.dmg`, drag **Folio** into your Applications folder, and open it from there. You should not see any warning. If you do, stop and tell me, because that means something is wrong with the file you downloaded.

## Windows
Run the `.exe`. **Windows will show you a blue box that says "Windows protected your PC."** This is expected. Click **More info**, then **Run anyway**.

### Why does that warning appear?
Windows shows it for any program it has not seen many people install before. Software companies make it go away by buying a *code signingcertificate*, which costs several hundred dollars a year. Folio is free and open source, made by one person for educational purposes, making the purchase of a code signing certificate pointless at this time. 

The warning appears once, when you install. After that Folio opens normally, like any other program.

### To my students in particular
This warning has a purpose: protection from malicious software. It is Windows telling you it cannot vouch for this file—and much of the time, that is a warning you should take seriously. In this case, though, you know where this file came from: you got the link from me personally and you downloaded it from that link. So: click through this one, and keep being suspicious of the next one. If a program you you cannot vouch for produces this warning, click cancel.

## If something goes wrong
Tell me what you did and what you saw, and bring the machine if you can. "It didn't work" is hard to fix; "I clicked Export and it said Pandoc not found" takes about a minute.
