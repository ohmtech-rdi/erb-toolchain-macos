#!/usr/bin/env python3
#
#     build.py
#     Copyright (c) 2020 Raphael DINGE
#
#Tab=3---------------------------------------------------------------------



##### IMPORT #################################################################

import os
import requests
import shutil
import subprocess
import sys
import tarfile

PATH_THIS = os.path.abspath (os.path.dirname (__file__))
PATH_ARTIFACTS = os.path.join (PATH_THIS, 'artifacts')
PATH_BIN = os.path.join (PATH_THIS, 'bin')



##############################################################################

if sys.version_info < (3, 6):
   print ('This script requires python 3.6 or greater.', file=sys.stderr)
   sys.exit (1)

##############################################################################

#-- download_brew_package ----------------------------------------------------

def download_brew_package (name, package_sha256):
   url = f'https://ghcr.io/v2/homebrew/core/{name}/blobs/sha256:{package_sha256}'
   headers = {'Authorization': 'Bearer QQ=='}

   filename = os.path.join (PATH_ARTIFACTS, f'{package_sha256}.tar')

   with requests.get (url, headers=headers, stream=True) as r:
      r.raise_for_status ()
      with open (filename, 'wb') as f:
         for chunk in r.iter_content (chunk_size=8192):
            f.write (chunk)


#-- extract_brew_package -----------------------------------------------------

def extract_brew_package (name, package_sha256, os_arch):
   filename = os.path.join (PATH_ARTIFACTS, f'{package_sha256}.tar')
   output_dir = os.path.join (PATH_ARTIFACTS, os_arch)
   if not os.path.exists (output_dir):
      os.makedirs (output_dir)

   with tarfile.open (filename, mode='r') as tf:
      tf.extractall (output_dir)


#-- build_dfu_util -----------------------------------------------------------

def build_dfu_util ():
   # https://formulae.brew.sh/api/formula/dfu-util.json
   name = 'dfu-util'

   package_sha256 = '5a5d86794a00b9559ffc819715c297da4f477296d20a92c804aefc426795d0b0'
   arch_os = 'x86_64_catalina'
   download_brew_package (name, package_sha256)
   extract_brew_package (name, package_sha256, arch_os)

   package_sha256 = 'c7dd53f422003b99c57f565aad8371e8cef1aa3de825f36cd927cd61ed64249d'
   arch_os = 'arm64_big_sur'
   download_brew_package (name, package_sha256)
   extract_brew_package (name, package_sha256, arch_os)

   amd64_bin = os.path.join (PATH_ARTIFACTS, 'x86_64_catalina', 'dfu-util', '0.11', 'bin', 'dfu-util')
   arm64_bin = os.path.join (PATH_ARTIFACTS, 'arm64_big_sur', 'dfu-util', '0.11', 'bin', 'dfu-util')

   subprocess.check_call (['chmod', '755', amd64_bin])
   subprocess.check_call (['chmod', '755', arm64_bin])

   subprocess.check_call ([
      'install_name_tool', '-add_rpath', '@executable_path/.',
      amd64_bin
   ])

   subprocess.check_call ([
      'install_name_tool', '-change',
      '@@HOMEBREW_PREFIX@@/opt/libusb/lib/libusb-1.0.0.dylib',
      '@rpath/libusb-1.0.0.dylib',
      amd64_bin
   ])

   subprocess.check_call ([
      'install_name_tool', '-add_rpath', '@executable_path/.',
      arm64_bin
   ])

   subprocess.check_call ([
      'install_name_tool', '-change',
      '@@HOMEBREW_PREFIX@@/opt/libusb/lib/libusb-1.0.0.dylib',
      '@rpath/libusb-1.0.0.dylib',
      arm64_bin
   ])

   universal_bin = os.path.join (PATH_BIN, 'dfu-util')

   subprocess.check_call ([
      'lipo', amd64_bin, arm64_bin,
      '-output', universal_bin,
      '-create'
   ])


#-- build_libusb -------------------------------------------------------------

def build_libusb ():
   # https://formulae.brew.sh/api/formula/libusb.json
   name = 'libusb'

   package_sha256 = '72ed40aec0356157f3d5071ecb28c481b3f3502985a320ec1848cdc8cf8483c1'
   arch_os = 'x86_64_catalina'
   download_brew_package (name, package_sha256)
   extract_brew_package (name, package_sha256, arch_os)

   package_sha256 = 'd9121e56c7dbfad640c9f8e3c3cc621d88404dc1047a4a7b7c82fe06193bca1f'
   arch_os = 'arm64_big_sur'
   download_brew_package (name, package_sha256)
   extract_brew_package (name, package_sha256, arch_os)

   amd64_bin = os.path.join (PATH_ARTIFACTS, 'x86_64_catalina', 'libusb', '1.0.26', 'lib', 'libusb-1.0.0.dylib')
   arm64_bin = os.path.join (PATH_ARTIFACTS, 'arm64_big_sur', 'libusb', '1.0.26', 'lib', 'libusb-1.0.0.dylib')

   subprocess.check_call (['chmod', '644', amd64_bin])
   subprocess.check_call (['chmod', '644', arm64_bin])

   subprocess.check_call ([
      'install_name_tool', '-id',
      'libusb-1.0.0.dylib',
      amd64_bin
   ])

   subprocess.check_call ([
      'install_name_tool', '-id',
      'libusb-1.0.0.dylib',
      arm64_bin
   ])

   universal_bin = os.path.join (PATH_BIN, 'libusb-1.0.0.dylib')

   subprocess.check_call ([
      'lipo', amd64_bin, arm64_bin,
      '-output', universal_bin,
      '-create'
   ])


#-- main ---------------------------------------------------------------------

def main ():
   if os.path.exists (PATH_BIN):
      shutil.rmtree (PATH_BIN)
   os.makedirs (PATH_BIN)

   if os.path.exists (PATH_ARTIFACTS):
      shutil.rmtree (PATH_ARTIFACTS)
   os.makedirs (PATH_ARTIFACTS)

   build_dfu_util ()
   build_libusb ()

   subprocess.check_call ([
      'tar', '-zcf',
      os.path.join (PATH_ARTIFACTS, 'toolchain_macos.tar.gz'),
      '-C', PATH_THIS,
      'bin'
   ])



#--------------------------------------------------------------------------

if __name__ == '__main__':
   sys.exit (main ())

