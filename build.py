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
      version += '_' + formula ['revision']
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


#-- add_rpath ----------------------------------------------------------------

def add_rpath (info, item):
   for arch_os in ARCH_OSES:
      bin = os.path.join (PATH_ARTIFACTS, arch_os, info ['name'], info ['version'], item)
      subprocess.check_call ([
         'install_name_tool', '-add_rpath', '@executable_path/.',
         bin
      ])


#-- change_rpath -------------------------------------------------------------

def change_rpath (info, item):
   for arch_os in ARCH_OSES:
      bin = os.path.join (PATH_ARTIFACTS, arch_os, info ['name'], info ['version'], item)
      output = subprocess.check_output (['otool', '-L', bin]).decode (sys.stdout.encoding)
      lines = output.split ('\n')
      for line in lines:
         line = line.strip ()
         path = line.split (' ')[0]
         if '@@HOMEBREW_PREFIX@@' in path:
            lib = path.split ('/')[-1]
            subprocess.check_call (['install_name_tool', '-change', path, f'@rpath/{lib}', bin])


#-- pack ---------------------------------------------------------------------

def pack (info, item):
   bins = map (lambda arch_os: os.path.join (PATH_ARTIFACTS, arch_os, info ['name'], info ['version'], item), ARCH_OSES)
   name = item.split ('/')[-1]
   subprocess.check_call ([
      'lipo', *bins,
      '-output', os.path.join (PATH_BIN, name),
      '-create'
   ])


#-- build_dfu_util -----------------------------------------------------------

def build_dfu_util ():
   info = get_formula_info ('dfu-util')
   download_formula (info)
   item = 'bin/dfu-util'
   allow_write_exec (info, item)
   add_rpath (info, item)
   change_rpath (info, item)
   pack (info, item)


#-- build_libusb -------------------------------------------------------------

def build_libusb ():
   info = get_formula_info ('libusb')
   download_formula (info)
   item = 'lib/libusb-1.0.0.dylib'
   allow_write_dylib (info, item)
   change_rpath (info, item)
   pack (info, item)


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

