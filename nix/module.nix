inputs: {
  config,
  lib,
  pkgs,
  options,
  ...
}:
with lib; let
  cfg = config.programs.auto-cpufreq;
  inherit (pkgs.stdenv.hostPlatform) system;
  defaultPackage = inputs.self.packages.${system}.default;
  cfgFilename = "auto-cpufreq.conf";
  cfgFile = format.generate cfgFilename cfg.settings;

  format = pkgs.formats.ini {};
in {
  options.programs.auto-cpufreq = {
    enable = mkEnableOption "Automatic CPU speed & power optimizer for Linux";

    settings = mkOption {
      description = mdDoc ''
        Configuration for `auto-cpufreq`.

        See its [example configuration file] for supported settings.
        [example configuration file]: https://github.com/AdnanHodzic/auto-cpufreq/blob/master/auto-cpufreq.conf-example
      '';

      default = {};
      type = types.submodule {freeformType = format.type;};
    };
  };

  config = mkIf cfg.enable {
    environment.systemPackages = [defaultPackage];

    services.auto-cpufreq.enable = true;
    systemd.services.auto-cpufreq = {
      overrideStrategy = "asDropin";
      serviceConfig.ExecStart = mkForce [
        ""
        "${defaultPackage}/bin/auto-cpufreq --daemon --config ${cfgFile}"
      ];
    };
  };
}
