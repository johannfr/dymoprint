{
  description = "CLI to print labels on a DYMO LetraTag 200B Bluetooth printer";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];

      forAllSystems = nixpkgs.lib.genAttrs systems;

      mkPkgSet =
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          py = pkgs.python3Packages;

          # dymo-bluetooth declares `bleak~=1.1.1`, but nixpkgs 26.05 ships
          # bleak 2.x. A BLE transport library is too risky to relax across a
          # major version, so we vendor the exact pinned version instead of
          # using nixpkgs' bleak. See CLAUDE.md "Packaging decisions".
          bleakPinned = py.buildPythonPackage {
            pname = "bleak";
            version = "1.1.1";
            format = "wheel";
            src = pkgs.fetchurl {
              url = "https://files.pythonhosted.org/packages/81/5a/c3378ba7b05abc7c2d95ae492eac0523d937c77afcb9ff7e7f67fe2ca11d/bleak-1.1.1-py3-none-any.whl";
              hash = "sha256-5gE3E5bjV9le48JW22W32mJMlO9vBR1H386T6oNhwi4=";
            };
            propagatedBuildInputs =
              pkgs.lib.optionals pkgs.stdenv.isLinux [ py.dbus-fast ]
              ++ pkgs.lib.optionals pkgs.stdenv.isDarwin [
                py.pyobjc-core
                py.pyobjc-framework-CoreBluetooth
                py.pyobjc-framework-libdispatch
              ];
            doCheck = false;
            pythonImportsCheck = [ "bleak" ];
          };

          dymoBluetooth = py.buildPythonPackage {
            pname = "dymo-bluetooth";
            version = "0.1.3";
            format = "wheel";
            src = pkgs.fetchurl {
              url = "https://files.pythonhosted.org/packages/68/1d/dca5f5b571b09d0241e1e1ceffec44d3422504cfaa057aff901159e8f6e3/dymo_bluetooth-0.1.3-py3-none-any.whl";
              hash = "sha256-cfTSkOk06OJkeIR8tqDeGFblJmqdF8mlXMlwGCLKAL4=";
            };
            propagatedBuildInputs = [
              bleakPinned
              py.pillow
            ];
            # dymo-bluetooth pins pillow~=11.0.0; the APIs it actually uses
            # (Image.convert("1"), ImageChops, crop, getpixel) are stable
            # basics, so we relax this pin instead of vendoring Pillow too.
            pythonRelaxDeps = [ "pillow" ];
            doCheck = false;
            pythonImportsCheck = [ "dymo_bluetooth" ];
          };

          liberationDir = pkgs.liberation_ttf;
          dejavuDir = pkgs.dejavu_fonts;

          pythonEnv = pkgs.python3.withPackages (ps: [
            dymoBluetooth
            ps.click
          ]);

          dymoprint = pkgs.stdenv.mkDerivation {
            pname = "dymoprint";
            version = "0.1.0";
            # Excludes stray __pycache__/*.pyc that Python may leave behind in
            # the working tree (e.g. from running the CLI directly during
            # development) -- those would otherwise get copied into the
            # store and shadow freshly-substituted sources (see fonts.py).
            src = pkgs.lib.cleanSourceWith {
              src = ./.;
              filter =
                path: type:
                !(type == "directory" && baseNameOf path == "__pycache__")
                && !(pkgs.lib.hasSuffix ".pyc" path);
            };

            nativeBuildInputs = [ pkgs.makeWrapper ];

            # Bake the real Nix store paths of our curated fonts into fonts.py,
            # replacing the placeholders described in CLAUDE.md.
            postPatch = ''
              substituteInPlace dymoprint/fonts.py \
                --replace-fail '@liberation_ttf@' '${liberationDir}' \
                --replace-fail '@dejavu_fonts@' '${dejavuDir}'
            '';

            dontBuild = true;

            installPhase = ''
              runHook preInstall

              site_packages=$out/${pythonEnv.sitePackages}
              mkdir -p $site_packages
              cp -r dymoprint $site_packages/

              # -P keeps Python from prepending the current working directory to
              # sys.path (which `-m` does by default) -- without it, running
              # `dymoprint` from inside a checkout of this repo would let the
              # raw source's ./dymoprint/ shadow this installed, substituted copy.
              makeWrapper ${pythonEnv.interpreter} $out/bin/dymoprint \
                --add-flags "-P -m dymoprint.main" \
                --prefix PYTHONPATH : $site_packages

              runHook postInstall
            '';
          };
        in
        {
          inherit
            pkgs
            pythonEnv
            dymoprint
            liberationDir
            dejavuDir
            ;
        };
    in
    {
      packages = forAllSystems (
        system:
        let
          pkgSet = mkPkgSet system;
        in
        {
          default = pkgSet.dymoprint;
          dymoprint = pkgSet.dymoprint;
        }
      );

      apps = forAllSystems (
        system:
        let
          pkgSet = mkPkgSet system;
        in
        {
          default = {
            type = "app";
            program = "${pkgSet.dymoprint}/bin/dymoprint";
          };
        }
      );

      devShells = forAllSystems (
        system:
        let
          pkgSet = mkPkgSet system;
        in
        {
          default = pkgSet.pkgs.mkShell {
            buildInputs = [ pkgSet.pythonEnv ];

            # Mirrors what postPatch bakes into the built package, so
            # `python -m dymoprint.main` works directly from the source tree.
            shellHook = ''
              export DYMOPRINT_LIBERATION_DIR="${pkgSet.liberationDir}"
              export DYMOPRINT_DEJAVU_DIR="${pkgSet.dejavuDir}"
            '';
          };
        }
      );
    };
}
