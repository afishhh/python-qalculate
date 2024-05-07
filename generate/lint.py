import re


_INCLUDE_REGEX = re.compile(r"\s*#\s*include\s+(.*)\s*$", flags=re.MULTILINE)

def lint_cpp(source: str, filename: str) -> bool:
    ok = True

    if filename.endswith("/pybind.hh"):
        matches = _INCLUDE_REGEX.findall(source)
        pybind_hh_included = False
        for match in matches:
            assert isinstance(match, str)
            if "pybind11/" in match and not pybind_hh_included:
                print(f'{filename}: \x1b[1;31merror:\x1b[0m pybind11 header {match} included before "pybind.hh"')
                ok = False
                break
            elif match == '"pybind.hh"':
                pybind_hh_included = True

    return ok
