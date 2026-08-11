on run argv
    if (count of argv) is less than 2 then
        error "Usage: fetch_with_safari.applescript <URL> <output-file>"
    end if

    set targetURL to item 1 of argv
    set outputPath to item 2 of argv
    set pageHTML to ""
    set pageTitle to ""

    tell application "Safari"
        activate
        if (count of documents) is 0 then
            make new document
        end if
        set URL of front document to targetURL
    end tell

    -- Wait up to two minutes for Cloudflare to clear and the real WebTrac
    -- schedule page to load in the normal Safari session.
    repeat with attempt from 1 to 120
        delay 1
        try
            tell application "Safari"
                set pageTitle to name of front document
                set pageHTML to source of front document
            end tell

            if pageTitle is not "Just a moment..." and pageHTML does not contain "challenges.cloudflare.com" then
                if pageHTML contains "Sultans" then exit repeat
            end if
        end try
    end repeat

    if pageHTML is "" then
        error "Safari returned no page source."
    end if

    if pageTitle is "Just a moment..." or pageHTML contains "challenges.cloudflare.com" then
        error "Cloudflare challenge is still displayed in Safari. Complete the verification in Safari, then run refresh_local.sh again."
    end if

    if pageHTML does not contain "Sultans" then
        error "Safari loaded a page, but the Sultans schedule was not found. Current page title: " & pageTitle
    end if

    set outFile to open for access POSIX file outputPath with write permission
    try
        set eof outFile to 0
        write pageHTML to outFile as «class utf8»
        close access outFile
    on error errMsg number errNum
        try
            close access outFile
        end try
        error errMsg number errNum
    end try

    return "Saved Safari page source to " & outputPath
end run
