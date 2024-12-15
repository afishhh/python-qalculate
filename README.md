> [!WARNING]
> This project is ~~under heavy development!~~ abandoned.
>
> Breaking changes may be introduced at any moment.

**WIP** Python bindings for [libqalculate](https://github.com/qalculate/libqalculate).

## Building

### Debian and derivatives

#### Dependencies

For the bindings only:
```command
sudo apt install build-essential cmake python3 python3-dev python3-pybind11 pybind11-dev
```

For libqalculate (when building with -DUSE_SYSTEM_LIBQALCULATE=OFF):
```command
sudo apt install autoconf intltool libtool automake libgmp-dev libmpfr-dev libcurl4-openssl-dev libicu-dev libxml2-dev
```

#### Building

```command
mkdir build && cd build
cmake ..
cmake --build . -j $(nproc)
```

### Nix(OS)

The package in the flake is still a work in progress, it is not a proper python package.
