{
    inputs = {
        nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    };

    outputs = {self, nixpkgs}@inputs :
    let
        system = "x86_64-linux"; # replace this as needed
        pkgs = nixpkgs.legacyPackages.${system};
        auto-cpufreq = pkgs.python3Packages.callPackage ./nix/default.nix {};
    in {
        packages.${system}.default = auto-cpufreq; 

	    devShells.${system}.default = pkgs.mkShell {
		    inputsFrom = [ auto-cpufreq ];
            packages = [ pkgs.python310Packages.pip ];
	    };

        nixosModules.default = import ./nix/module.nix inputs;
    };
}
