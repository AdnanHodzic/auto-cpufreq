{ fetchPypi, python310Packages}:

python310Packages.buildPythonPackage rec {
    pname = "setuptools-git-versioning";
    version = "1.13.5";
    src = fetchPypi {
        inherit pname version;
        sha256 = "af9ad1e8103b5abb5b128c2db4fef99407328ac9c12f65d3ff9550c4bb39ad1c";
    };
    propagatedBuildInputs = with python310Packages; [ toml packaging];
}