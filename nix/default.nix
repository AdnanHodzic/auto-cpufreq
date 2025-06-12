{
  lib,
  python3Packages,
  pkgs,
  fetchFromGitHub,
  fetchPypi,
}:
let

  pyinotify = python3Packages.pyinotify.overrideAttrs (oldAttrs: {
    src = fetchFromGitHub {
      owner = "shadeyg56";
      repo = "pyinotify-3.12";
      rev = "923cebec3a2a84c7e38c9e68171eb93f5d07ce5d";
      hash = "sha256-714CximEK4YhIqDmvqJYOUGs39gvDkWGrkNrXwxT8iM=";
    };
    patches = [];
  });

  requests = python3Packages.requests.overrideAttrs (oldAttrs: rec {
    version = "2.32.4";
    src = fetchPypi {
      pname = "requests";
      inherit version;
      hash = "sha256-J9AxZoLIopg00yZIIAJLYqNpQgg9Usry8UwFkTNtNCI=";
    };
  });

in
python3Packages.buildPythonPackage {
  # use pyproject.toml instead of setup.py
  format = "pyproject";

  pname = "auto-cpufreq";
  version = "2.6.0";
  src = ../.;

  nativeBuildInputs = with pkgs; [wrapGAppsHook gobject-introspection];

  buildInputs = with pkgs; [gtk3 python3Packages.poetry-core];

  propagatedBuildInputs = with python3Packages; [requests pygobject3 click distro psutil setuptools poetry-dynamic-versioning pyinotify urwid pyasyncore pkgs.getent];  

  doCheck = false;
  pythonImportsCheck = ["auto_cpufreq"];

  patches = [
    # patch to prevent script copying and to disable install
    ./patches/prevent-install-and-copy.patch
  ];

  postPatch = ''
    substituteInPlace auto_cpufreq/core.py --replace-fail '/opt/auto-cpufreq/override.pickle' /var/run/override.pickle
    substituteInPlace scripts/org.auto-cpufreq.pkexec.policy --replace-fail "/opt/auto-cpufreq/venv/bin/auto-cpufreq" $out/bin/auto-cpufreq

    substituteInPlace auto_cpufreq/gui/app.py auto_cpufreq/gui/objects.py --replace-fail "/usr/local/share/auto-cpufreq/images/icon.png" $out/share/pixmaps/auto-cpufreq.png
    substituteInPlace auto_cpufreq/gui/app.py --replace-fail "/usr/local/share/auto-cpufreq/scripts/style.css" $out/share/auto-cpufreq/scripts/style.css
  '';

  postInstall = ''
    # copy script manually
    cp scripts/cpufreqctl.sh $out/bin/cpufreqctl.auto-cpufreq

    # move the css to the right place
    mkdir -p $out/share/auto-cpufreq/scripts
    cp scripts/style.css $out/share/auto-cpufreq/scripts/style.css

    # systemd service
    mkdir -p $out/lib/systemd/system
    cp scripts/auto-cpufreq.service $out/lib/systemd/system

    # desktop icon
    mkdir -p $out/share/applications
    mkdir $out/share/pixmaps
    cp scripts/auto-cpufreq-gtk.desktop $out/share/applications
    cp images/icon.png $out/share/pixmaps/auto-cpufreq.png

    # polkit policy
    mkdir -p $out/share/polkit-1/actions
    cp scripts/org.auto-cpufreq.pkexec.policy $out/share/polkit-1/actions
  '';

  meta = {
    homepage = "https://github.com/AdnanHodzic/auto-cpufreq";
    description = "Automatic CPU speed & power optimizer for Linux";
    license = lib.licenses.lgpl3Plus;
    platforms = lib.platforms.linux;
    maintainers = with lib.maintainers; [Technical27];
    mainProgram = "auto-cpufreq";
  };
}
