rye fmt
rye sync
rye build --clean
rye publish -r testpypi --repository-url https://test.pypi.org/legacy/
@REM rye publish 