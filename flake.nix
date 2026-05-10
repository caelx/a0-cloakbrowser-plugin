{
  description = "CloakBrowser Agent Zero plugin development shell";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs =
    { nixpkgs, ... }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
    in
    {
      devShells = forAllSystems (
        system:
        let
          pkgs = import nixpkgs { inherit system; };
          runtimeLibs = with pkgs; [
            alsa-lib
            at-spi2-atk
            at-spi2-core
            cairo
            cups
            dbus
            expat
            fontconfig
            freetype
            gdk-pixbuf
            glib
            gtk3
            libdrm
            libgbm
            libGL
            libxkbcommon
            nspr
            nss
            pango
            udev
            libx11
            libxcb
            libxcomposite
            libxcursor
            libxdamage
            libxext
            libxfixes
            libxi
            libxrandr
            libxrender
            libxscrnsaver
            libxtst
          ];
        in
        {
          default = pkgs.mkShell {
            packages = with pkgs; [
              bashInteractive
              chromium
              docker-client
              file
              gh
              git
              jq
              lsof
              procps
              psmisc
              python312
              python312Packages.pytest
              ripgrep
              ruff
              strace
              uv
              xorg-server
            ];

            LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath runtimeLibs;

            shellHook = ''
              export UV_PROJECT_ENVIRONMENT="$PWD/.venv"
              export UV_PYTHON="${pkgs.python312}/bin/python3"
              export PATH="$PWD/.venv/bin:$PATH"
              export PLAYWRIGHT_BROWSERS_PATH="$PWD/.playwright"
              export CLOAKBROWSER_CACHE_DIR="$PWD/.cloakbrowser/cache"

              if [ ! -x "$PWD/.venv/bin/python" ]; then
                uv venv --python "$UV_PYTHON" "$PWD/.venv" >/dev/null
              fi
              if ! "$PWD/.venv/bin/python" -c "import cloakbrowser" 2>/dev/null; then
                uv pip install --python "$PWD/.venv/bin/python" -r requirements-dev.txt
              fi
            '';
          };
        }
      );
    };
}
