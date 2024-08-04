{
  python3Packages,
  pkgs,
  ...
}: let
  mainPkg = python3Packages.callPackage ./default.nix {};
in
  mainPkg.overrideAttrs (oa: {
    nativeBuildInputs =
      [
        python3Packages.pip
        pkgs.poetry
      ]
      ++ (oa.nativeBuildInputs or []);
  })
