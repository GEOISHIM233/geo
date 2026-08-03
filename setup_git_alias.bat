@echo off
git config --global alias.auto "!git add . && git commit -m \"Auto-update\" && git push"
echo Git alias 'auto' has been set up successfully!
echo Usage: git auto
pause