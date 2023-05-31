#!/usr/bin/env python3
#
#     build.py
#     Copyright (c) 2020 Raphael DINGE
#
#Tab=3---------------------------------------------------------------------



##### IMPORT #################################################################

import json
import os
import requests
import shutil
import subprocess
import sys
import tarfile

PATH_THIS = os.path.abspath (os.path.dirname (__file__))
PATH_ARTIFACTS = os.path.join (PATH_THIS, 'artifacts')
PATH_BIN = os.path.join (PATH_THIS, 'bin')

ARCH_OSES = [
   'catalina',       # 10.15 x86_64
   'arm64_big_sur',  # 11 arm64
]



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


#-- get_formula_info ---------------------------------------------------------

def get_formula_info (name):
   r = requests.get (f'https://formulae.brew.sh/api/formula/{name}.json')
   formula = json.loads (r.content)
   version = formula ['versions']['stable']
   if formula ['revision'] != 0:
      version += '_' + str (formula ['revision'])
   return {
      'name': name,
      ARCH_OSES [0]: formula ['bottle']['stable']['files'][ARCH_OSES [0]]['sha256'],
      ARCH_OSES [1]: formula ['bottle']['stable']['files'][ARCH_OSES [1]]['sha256'],
      'version': version,
   }


#-- download_formula ---------------------------------------------------------

def download_formula (info):
   for arch_os in ARCH_OSES:
      download_brew_package (info ['name'], info [arch_os])
      extract_brew_package (info ['name'], info [arch_os], arch_os)


#-- allow_write_exec ---------------------------------------------------------

def allow_write_exec (info, item):
   for arch_os in ARCH_OSES:
      bin = os.path.join (PATH_ARTIFACTS, arch_os, info ['name'], info ['version'], item)
      subprocess.check_call (['chmod', '755', bin])


#-- allow_write_dylib --------------------------------------------------------

def allow_write_dylib (info, item):
   for arch_os in ARCH_OSES:
      bin = os.path.join (PATH_ARTIFACTS, arch_os, info ['name'], info ['version'], item)
      subprocess.check_call (['chmod', '644', bin])


#-- set_id -------------------------------------------------------------------

def set_id (info, item):
   for arch_os in ARCH_OSES:
      bin = os.path.join (PATH_ARTIFACTS, arch_os, info ['name'], info ['version'], item)
      subprocess.check_call ([
         'install_name_tool', '-id', item.split ('/')[-1],
         bin
      ])


#-- set_dependent_shared_lib_erb ---------------------------------------------

def set_dependent_shared_lib_erb (info, item):
   for arch_os in ARCH_OSES:
      bin = os.path.join (PATH_ARTIFACTS, arch_os, info ['name'], info ['version'], item)
      output = subprocess.check_output (['otool', '-L', bin]).decode (sys.stdout.encoding)
      lines = output.split ('\n')
      for line in lines:
         line = line.strip ()
         path = line.split (' ')[0]
         if '@@HOMEBREW_' in path: # @@HOMEBREW_PREFIX@@ or @@HOMEBREW_CELLAR@@
            lib = path.split ('/')[-1]
            subprocess.check_call (['install_name_tool', '-change', path, f'@@ERB@@/{lib}', bin])


#-- pack ---------------------------------------------------------------------

def pack (info, item):
   bins = map (lambda arch_os: os.path.join (PATH_ARTIFACTS, arch_os, info ['name'], info ['version'], item), ARCH_OSES)
   name = item.split ('/')[-1]
   subprocess.check_call ([
      'lipo', *bins,
      '-output', os.path.join (PATH_BIN, name),
      '-create'
   ])


#-- build_cairo --------------------------------------------------------------

def build_cairo ():
   info = get_formula_info ('cairo')
   download_formula (info)
   item = 'lib/libcairo.2.dylib'
   allow_write_dylib (info, item)
   set_id (info, item)
   set_dependent_shared_lib_erb (info, item)
   pack (info, item)


#-- build_libpng -------------------------------------------------------------

def build_libpng ():
   # catalina disappeared in the latest update, but it was in 1.6.39 for some time
   info = {
      'name': 'libpng',
      'catalina': '13780286d987167f7e50aea65947e1460a6616d0f1b224b37f8351775eab72f3',
      'arm64_big_sur': 'cf59cedc91afc6f2f3377567ba82b99b97744c60925a5d1df6ecf923fdb2f234',
      'version': '1.6.39',
   }
   download_formula (info)
   item = 'lib/libpng16.16.dylib'
   allow_write_dylib (info, item)
   set_id (info, item)
   set_dependent_shared_lib_erb (info, item)
   pack (info, item)


#-- build_freetype -----------------------------------------------------------

def build_freetype ():
   # catalina disappeared in the latest update, so take 2.12.1
   info = {
      'name': 'freetype',
      'catalina': 'cafa6fee3a0ca54b1659f433667a145acef2c2d2061292d2f8bc088db7f0ea4f',
      'arm64_big_sur': 'deb09510fb83adf76d9bb0d4ac4a3d3a2ddfff0d0154e09d3719edb73b058278',
      'version': '2.12.1',
   }
   download_formula (info)
   item = 'lib/libfreetype.6.dylib'
   allow_write_dylib (info, item)
   set_id (info, item)
   set_dependent_shared_lib_erb (info, item)
   pack (info, item)


#-- build_fontconfig ---------------------------------------------------------

def build_fontconfig ():
   # catalina disappeared in the latest update, so take 2.14.1
   info = {
      'name': 'fontconfig',
      'catalina': '1d6767bcdcf4390f88c120ca0beff6104d3339880950342802ad8b4b51520a6e',
      'arm64_big_sur': '143b68331a6332cc0e1e3883e2863d65139869ac5bf1823bbe49fd2127d2c7f5',
      'version': '2.14.1',
   }
   download_formula (info)
   item = 'lib/libfontconfig.1.dylib'
   allow_write_dylib (info, item)
   set_id (info, item)
   set_dependent_shared_lib_erb (info, item)
   pack (info, item)


#-- build_pixman -------------------------------------------------------------

def build_pixman ():
   # catalina disappeared in the latest update, so take 0.40.0
   info = {
      'name': 'pixman',
      'catalina': '1862e6826a4bedb97af8dcb9ab849c69754226ed92e5ee19267fa33ee96f94f8',
      'arm64_big_sur': 'da951aa8e872276034458036321dfa78e7c8b5c89b9de3844d3b546ff955c4c3',
      'version': '0.40.0',
   }
   download_formula (info)
   item = 'lib/libpixman-1.0.dylib'
   allow_write_dylib (info, item)
   set_id (info, item)
   set_dependent_shared_lib_erb (info, item)
   pack (info, item)


#-- build_libxcb -------------------------------------------------------------

def build_libxcb ():
   # catalina disappeared in the latest update, so take 1.15
   info = {
      'name': 'libxcb',
      'catalina': '035b1d299e3f1b41581e759981cf9a83aee2754c4b744cdcad4c7fe32de83ffb',
      'arm64_big_sur': '6bf77051114dec12e0c541bc478d7833a992792047553fc821f3e1a17b82ec38',
      'version': '1.15',
   }
   download_formula (info)
   items = [
      'lib/libxcb-shm.0.dylib',
      'lib/libxcb.1.dylib',
      'lib/libxcb-render.0.dylib',
   ]
   for item in items:
      allow_write_dylib (info, item)
      set_id (info, item)
      set_dependent_shared_lib_erb (info, item)
      pack (info, item)


#-- build_libx11 -------------------------------------------------------------

def build_libx11 ():
   # catalina disappeared in the latest update, so take 1.8.2
   info = {
      'name': 'libx11',
      'catalina': '83b5c84a2f595ddb273b9eb9790109e542da3c21832df5cc6c90a1c328050389',
      'arm64_big_sur': '4448aa22e8118de5775caf8488b666a211b01f50085a418fbbbcbfed2d83e517',
      'version': '1.8.2',
   }
   download_formula (info)
   item = 'lib/libX11.6.dylib'
   allow_write_dylib (info, item)
   set_id (info, item)
   set_dependent_shared_lib_erb (info, item)
   pack (info, item)


#-- build_libxext ------------------------------------------------------------

def build_libxext ():
   info = get_formula_info ('libxext')
   download_formula (info)
   item = 'lib/libXext.6.dylib'
   allow_write_dylib (info, item)
   set_id (info, item)
   set_dependent_shared_lib_erb (info, item)
   pack (info, item)


#-- build_libxrender ---------------------------------------------------------

def build_libxrender ():
   # catalina disappeared in the latest update, so take 0.9.10
   info = {
      'name': 'libxrender',
      'catalina': 'cb7f48876d362f919ed1c34ece8ec5abb16f6e414a6119655e3948fffab5dfab',
      'arm64_big_sur': '46243f05a17674c00950dddc105b33aa479af7d605533d1aeada27d4d89d4275',
      'version': '0.9.10',
   }
   download_formula (info)
   item = 'lib/libXrender.1.dylib'
   allow_write_dylib (info, item)
   set_id (info, item)
   set_dependent_shared_lib_erb (info, item)
   pack (info, item)


#-- build_libxau -------------------------------------------------------------

def build_libxau ():
   # catalina disappeared in the latest update, so take 1.0.10
   info = {
      'name': 'libxau',
      'catalina': '1fc57a7cb97c7e4eecbd4b569070c36d12d9dd7f0d185a6513edf3fdc1b5696a',
      'arm64_big_sur': '3f1c2890d5906b1e7562d6d8fac52f55f92fc88eb606fde7a15585327ed02e92',
      'version': '1.0.10',
   }
   download_formula (info)
   item = 'lib/libXau.6.dylib'
   allow_write_dylib (info, item)
   set_id (info, item)
   set_dependent_shared_lib_erb (info, item)
   pack (info, item)


#-- build_libxdmcp -----------------------------------------------------------

def build_libxdmcp ():
   # catalina disappeared in the latest update, so take 1.1.3
   info = {
      'name': 'libxdmcp',
      'catalina': '123c77fba2179591f3c1588808f33d231e9e04d8a91c99f6684d2c7eb64626b0',
      'arm64_big_sur': '6c17c65a3f5768a620bc177f6ee189573993df7337c6614050c28e400dc6320c',
      'version': '1.1.3',
   }
   download_formula (info)
   item = 'lib/libXdmcp.6.dylib'
   allow_write_dylib (info, item)
   set_id (info, item)
   set_dependent_shared_lib_erb (info, item)
   pack (info, item)


#-- build_dfu_util -----------------------------------------------------------

def build_dfu_util ():
   info = get_formula_info ('dfu-util')
   download_formula (info)
   item = 'bin/dfu-util'
   allow_write_exec (info, item)
   set_dependent_shared_lib_erb (info, item)
   pack (info, item)


#-- build_libusb -------------------------------------------------------------

def build_libusb ():
   info = get_formula_info ('libusb')
   download_formula (info)
   item = 'lib/libusb-1.0.0.dylib'
   allow_write_dylib (info, item)
   set_id (info, item)
   set_dependent_shared_lib_erb (info, item)
   pack (info, item)


#-- main ---------------------------------------------------------------------

def main ():
   if os.path.exists (PATH_BIN):
      shutil.rmtree (PATH_BIN)
   os.makedirs (PATH_BIN)

   if os.path.exists (PATH_ARTIFACTS):
      shutil.rmtree (PATH_ARTIFACTS)
   os.makedirs (PATH_ARTIFACTS)

   build_cairo ()
   build_libpng ()
   build_freetype ()
   build_fontconfig ()
   build_pixman ()
   build_libxcb ()
   build_libx11 ()
   build_libxext ()
   build_libxrender ()
   build_libxau ()
   build_libxdmcp ()

   build_dfu_util ()
   build_libusb ()

   subprocess.check_call (
      ['ln', '-s', 'libcairo.2.dylib', 'libcairo.dylib'],
      cwd=PATH_BIN
   )

   subprocess.check_call (
      ['ln', '-s', 'libfreetype.6.dylib', 'libfreetype.dylib'],
      cwd=PATH_BIN
   )

   subprocess.check_call ([
      'tar', '-zcf',
      os.path.join (PATH_ARTIFACTS, 'toolchain_macos.tar.gz'),
      '-C', PATH_THIS,
      'bin'
   ])



#--------------------------------------------------------------------------

if __name__ == '__main__':
   sys.exit (main ())

