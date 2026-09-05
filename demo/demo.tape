# Generate the README GIF with VHS (https://github.com/charmbracelet/vhs):
#     vhs demo/demo.tape        ->  writes demo/standin.gif
#
# It records `python demo/demo.py`, which shows: first run hits the (stand-in)
# API and records (~8s), every run after replays from the cassette (~0.03s).

Output demo/standin.gif

Set Shell "bash"
Set FontSize 22
Set Width 1200
Set Height 460
Set Theme "Dracula"
Set Padding 20
Set TypingSpeed 55ms

# Hidden setup so the visible command stays clean (no install needed).
Hide
Type "export PYTHONPATH=$PWD"
Enter
Type "clear"
Enter
Show

Type "python demo/demo.py"
Sleep 600ms
Enter
Sleep 14s
