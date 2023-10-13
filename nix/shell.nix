{
  python310Packages,
  python3Packages,
  ...
}: let
  mainPkg = python3Packages.callPackage ./default.nix {};
in
  mainPkg.overrideAttrs (oa: {
    nativeBuildInputs =
      [
        python310Packages.pip
      ]
      ++ (oa.nativeBuildInputs or []);
  })
