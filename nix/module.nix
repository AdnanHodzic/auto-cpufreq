inputs: {
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.programs.auto-cpufreq;
  inherit (pkgs.stdenv.hostPlatform) system;
  defaultPackage = inputs.self.packages.${system}.default;
  cfgFilename = "auto-cpufreq.conf";
  cfgFile = format.generate cfgFilename cfg.settings;

  inherit (lib) types;
  inherit (lib.modules) mkIf mkForce;
  inherit (lib.options) mkOption mkEnableOption;

  format = pkgs.formats.ini {};
in {
  options.programs.auto-cpufreq = {
    enable = mkEnableOption "Automatic CPU speed & power optimizer for Linux";

    settings = mkOption {
      description = ''
        Configuration for `auto-cpufreq`.

        See its [example configuration file] for supported settings.
        [example configuration file]: https://github.com/AdnanHodzic/auto-cpufreq/blob/master/auto-cpufreq.conf
      '';

      default = {};
      type = types.submodule {freeformType = format.type;};
    };
  };

  config = mkIf cfg.enable {
    environment.systemPackages = [ defaultPackage ];

    systemd = {
      packages =  [ defaultPackage ];
      services.auto-cpufreq = {
        wantedBy = [ "multi-user.target" ];
        path = with pkgs; [ bash coreutils ];
        overrideStrategy = "asDropin";

        serviceConfig.WorkingDirectory = "";
        serviceConfig.ExecStart = mkForce [
          ""
          "${defaultPackage}/bin/auto-cpufreq --daemon --config ${cfgFile}"
        ];
      };
    };
  };
}
