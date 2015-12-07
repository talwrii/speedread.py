# speedread.py

The aim of this project is to create a *very* feature complete, command line
program for "speedreading" similar to spritz. Although maybe "movie reading"
is a better description of what spritz does.

It is largely based upon `https://github.com/pasky/speedread.git`
but rewritten in python with added overengineering
in preparation for feature creeping.

# Intended Features

* Spritz-clone (Done)
* Easy for people to make pull requests (Done - hopefully)
* Vim-like key bindings (Done)
* Works in pipelines (Not implemented)
* Instant start-up times for large documents (Done)
* Commands to repeat and skip sentences and paragraphs (Partial)
* Commands to display large quantities of text (Partial)
* Commands to search (Not implemented - but easy)
* As many other features as possible (Partial)

# Quickstart

    pip install https://github.com/talwrii/speedread.py#speedread
    pyspeedread --help
    pyspeedread text.txt
