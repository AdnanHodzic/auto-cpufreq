{
  lib,
  buildPythonPackage,
  poetry-core,
  pygobject3,
  click,
  distro,
  psutil,
  setuptools,
  poetry-dynamic-versioning,
  inotify-simple,
  urwid,
  requests,
  pkgs,
  fetchPypi,
}:
let

  requestsPatched = requests.overrideAttrs (oldAttrs: rec {
    version = "2.32.4";
    src = fetchPypi {
      pname = "requests";
      inherit version;
      hash = "sha256-J9AxZoLIopg00yZIIAJLYqNpQgg9Usry8UwFkTNtNCI=";
    };
    patches = [ ];
  });

in
buildPythonPackage rec {
  # use pyproject.toml instead of setup.py
  format = "pyproject";

  pname = "auto-cpufreq";
  version = "3.2.0";
  # Flake source trees do not contain Git metadata. Use the release version
  # already declared by this derivation instead of weakening strict source builds.
  POETRY_DYNAMIC_VERSIONING_BYPASS = version;
  src = ../.;

  nativeBuildInputs = with pkgs; [
    wrapGAppsHook3
    gobject-introspection
  ];

  buildInputs = [
    pkgs.gtk3
    poetry-core
  ];

  propagatedBuildInputs = [
    requestsPatched
    pygobject3
    click
    distro
    psutil
    setuptools
    poetry-dynamic-versioning
    inotify-simple
    urwid
    pkgs.getent
    pkgs.kmod
    pkgs.dmidecode
  ];

  doCheck = false;
  pythonImportsCheck = [ "auto_cpufreq" ];

  patches = [
    # patch to prevent script copying and to disable install
    ./patches/prevent-install-and-copy.patch
  ];

  postPatch = ''
    substituteInPlace auto_cpufreq/core.py --replace-fail '/opt/auto-cpufreq/override.pickle' /var/run/override.pickle
    substituteInPlace scripts/org.auto-cpufreq.pkexec.policy --replace-fail "/opt/auto-cpufreq/current/venv/bin/auto-cpufreq" $out/bin/auto-cpufreq

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
    license = lib.licenses.gpl3Plus;
    platforms = lib.platforms.linux;
    maintainers = with lib.maintainers; [ Technical27 ];
    mainProgram = "auto-cpufreq";
  };
}
