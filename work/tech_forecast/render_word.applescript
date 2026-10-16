on run argv
    set inputPath to item 1 of argv
    set outputPath to item 2 of argv
    set inputFile to POSIX file inputPath as alias
    set outputFile to POSIX file outputPath
    tell application "Microsoft Word"
        activate
        delay 3
        open inputFile
        delay 2
        set theDoc to active document
        save as theDoc file name outputFile file format format PDF
        close theDoc saving no
    end tell
end run
