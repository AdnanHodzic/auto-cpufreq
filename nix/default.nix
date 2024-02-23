{
  lib,
  python310Packages,
  pkgs,
}:
python310Packages.buildPythonPackage {
  # use pyproject.toml instead of setup.py
  format = "pyproject";

  pname = "auto-cpufreq";
  version = "2.2.0";
  src = ../.;

  nativeBuildInputs = with pkgs; [wrapGAppsHook gobject-introspection];

  buildInputs = with pkgs; [gtk3 python310Packages.poetry-core];

  propagatedBuildInputs = with python310Packages; [requests pygobject3 click distro psutil setuptools poetry-dynamic-versioning];

  doCheck = false;
  pythonImportsCheck = ["auto_cpufreq"];

  patches = [
    # patch to prevent script copying and to disable install
    ./patches/prevent-install-and-copy.patch
  ];

  postPatch = ''
    substituteInPlace auto_cpufreq/core.py --replace '/opt/auto-cpufreq/override.pickle' /var/run/override.pickle
    substituteInPlace scripts/org.auto-cpufreq.pkexec.policy --replace "/opt/auto-cpufreq/venv/bin/auto-cpufreq" $out/bin/auto-cpufreq

    substituteInPlace auto_cpufreq/gui/app.py auto_cpufreq/gui/objects.py --replace "/usr/local/share/auto-cpufreq/images/icon.png" $out/share/pixmaps/auto-cpufreq.png
    substituteInPlace auto_cpufreq/gui/app.py --replace "/usr/local/share/auto-cpufreq/scripts/style.css" $out/share/auto-cpufreq/scripts/style.css
  '';

  postInstall = ''
    # copy script manually
    cp scripts/cpufreqctl.sh $out/bin/cpufreqctl.auto-cpufreq

    # move the css to the rihgt place
    mkdir -p $out/share/auto-cpufreq/scripts
    cp scripts/style.css $out/share/auto-cpufreq/scripts/style.css

    # systemd service
    mkdir -p $out/lib/systemd/system
    cp scripts/auto-cpufreq.service $out/lib/systemd/system
    substituteInPlace $out/lib/systemd/system/auto-cpufreq.service --replace "/usr/local" $out

    # desktop icon
    mkdir -p $out/share/applications
    mkdir $out/share/pixmaps
    cp scripts/auto-cpufreq-gtk.desktop $out/share/applications
    cp images/icon.png $out/share/pixmaps/auto-cpufreq.png

    # polkit policy
    mkdir -p $out/share/polkit-1/actions
    cp scripts/org.auto-cpufreq.pkexec.policy $out/share/polkit-1/actions
  '';

  meta = with lib; {
    homepage = "https://github.com/AdnanHodzic/auto-cpufreq";
    description = "Automatic CPU speed & power optimizer for Linux";
    license = licenses.lgpl3Plus;
    platforms = platforms.linux;
    maintainers = [maintainers.Technical27];
    mainProgram = "auto-cpufreq";
  };
}
