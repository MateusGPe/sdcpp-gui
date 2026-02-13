poetry run isort . --profile black
poetry run black build.py sd-cpp-gui.spec
poetry run dmypy run -- ./sd_cpp_gui/
poetry run pylint $(git ls-files '*.py')