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

def extract_brew_package (name, package_sha256, arch_os):
   filename = os.path.join (PATH_ARTIFACTS, f'{package_sha256}.tar')
   output_dir = os.path.join (PATH_ARTIFACTS, arch_os)
   if not os.path.exists (output_dir):
      os.makedirs (output_dir)

   with tarfile.open (filename, mode='r') as tf:
      tf.extractall (output_dir)


#-- get_formula_info ---------------------------------------------------------

def get_formula_info (name, arch_oses):
   r = requests.get (f'https://formulae.brew.sh/api/formula/{name}.json')
   formula = json.loads (r.content)
   version = formula ['versions']['stable']
   if formula ['revision'] != 0:
      version += '_' + str (formula ['revision'])

   archs = list (map (
      lambda arch_os: { 'arch_os': arch_os, 'sha256': formula ['bottle']['stable']['files'][arch_os]['sha256'] },
      arch_oses
   ))

   return {
      'name': name,
      'version': version,
      'archs': archs,
   }


#-- download_formula ---------------------------------------------------------

def download_formula (info):
   name = info ['name']
   for arch in info ['archs']:
      arch_os = arch ['arch_os']
      sha256 = arch ['sha256']
      download_brew_package (name, sha256)
      extract_brew_package (name, sha256, arch_os)


#-- allow_write ---------------------------------------------------------

def allow_write (info, item):
   name = info ['name']
   version = info ['version']
   for arch in info ['archs']:
      arch_os = arch ['arch_os']
      bin = os.path.join (PATH_ARTIFACTS, arch_os, name, version, item)
      subprocess.check_call (['chmod', 'u+w', bin])


#-- set_id -------------------------------------------------------------------

def set_id (info, item):
   name = info ['name']
   version = info ['version']
   for arch in info ['archs']:
      arch_os = arch ['arch_os']
      bin = os.path.join (PATH_ARTIFACTS, arch_os, name, version, item)
      subprocess.check_call ([
         'install_name_tool', '-id', item.split ('/')[-1],
         bin
      ])


#-- set_dependent_shared_lib_erb ---------------------------------------------

def set_dependent_shared_lib_erb (info, item):
   name = info ['name']
   version = info ['version']
   for arch in info ['archs']:
      arch_os = arch ['arch_os']
      bin = os.path.join (PATH_ARTIFACTS, arch_os, name, version, item)
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
   name = info ['name']
   version = info ['version']
   archs = info ['archs']
   filename = item.split ('/')[-1]

   if len (archs) == 2:
      bins = map (lambda arch: os.path.join (PATH_ARTIFACTS, arch ['arch_os'], name, version, item), archs)
      subprocess.check_call ([
         'lipo', *bins,
         '-output', os.path.join (PATH_BIN, filename),
         '-create',
      ])
   else:
      assert len (archs) == 1
      arch_os = archs [0]['arch_os']
      shutil.copy (
         os.path.join (PATH_ARTIFACTS, arch_os, name, version, item),
         os.path.join (PATH_BIN, filename)
      )


#-- build_single_arch --------------------------------------------------------

def build_single_arch (name, arch_os, items, version=None, sha256=None):
   if version:
      info = {
         'name': name,
         'version': version,
         'archs': [{
            'arch_os': arch_os,
            'sha256': sha256
         }],
      }
   else:
      info = get_formula_info (name, [arch_os])

   download_formula (info)

   for item in items:
      type = item.split ('/')[0]
      if type in ['bin', 'lib']:
         allow_write (info, item)
         if type == 'lib':
            set_id (info, item)
         set_dependent_shared_lib_erb (info, item)
      pack (info, item)


#-- build_multi_arch ---------------------------------------------------------

def build_multi_arch (name, arch_oses, items):
   info = get_formula_info (name, arch_oses)
   download_formula (info)
   for item in items:
      type = item.split ('/')[0]
      if type in ['bin', 'lib']:
         allow_write (info, item)
         if type == 'lib':
            set_id (info, item)
         set_dependent_shared_lib_erb (info, item)
      pack (info, item)


#-- build_catalina -----------------------------------------------------------

def build_catalina ():
   if os.path.exists (PATH_BIN):
      shutil.rmtree (PATH_BIN)
   os.makedirs (PATH_BIN)

   arch_os = 'catalina'

   build_single_arch ('cairo', arch_os, ['lib/libcairo.2.dylib'])
   build_single_arch (
      'libpng', arch_os, ['lib/libpng16.16.dylib'], '1.6.39',
      '13780286d987167f7e50aea65947e1460a6616d0f1b224b37f8351775eab72f3'
   )
   build_single_arch (
      'freetype', arch_os, ['lib/libfreetype.6.dylib'], '2.12.1',
      'cafa6fee3a0ca54b1659f433667a145acef2c2d2061292d2f8bc088db7f0ea4f'
   )
   build_single_arch (
      'fontconfig', arch_os, ['lib/libfontconfig.1.dylib'], '2.14.1',
      '1d6767bcdcf4390f88c120ca0beff6104d3339880950342802ad8b4b51520a6e'
   )
   build_single_arch (
      'pixman', arch_os, ['lib/libpixman-1.0.dylib'], '0.40.0',
      '1862e6826a4bedb97af8dcb9ab849c69754226ed92e5ee19267fa33ee96f94f8'
   )
   build_single_arch (
      'libxcb', arch_os,
      ['lib/libxcb-shm.0.dylib', 'lib/libxcb.1.dylib', 'lib/libxcb-render.0.dylib'],
      '1.15', '035b1d299e3f1b41581e759981cf9a83aee2754c4b744cdcad4c7fe32de83ffb'
   )
   build_single_arch (
      'libx11', arch_os, ['lib/libX11.6.dylib'], '1.8.2',
      '83b5c84a2f595ddb273b9eb9790109e542da3c21832df5cc6c90a1c328050389'
   )
   build_single_arch ('libxext', arch_os, ['lib/libXext.6.dylib'])
   build_single_arch (
      'libxrender', arch_os, ['lib/libXrender.1.dylib'], '0.9.10',
      'cb7f48876d362f919ed1c34ece8ec5abb16f6e414a6119655e3948fffab5dfab'
   )
   build_single_arch (
      'libxau', arch_os, ['lib/libXau.6.dylib'], '1.0.10',
      '1fc57a7cb97c7e4eecbd4b569070c36d12d9dd7f0d185a6513edf3fdc1b5696a'
   )
   build_single_arch (
      'libxdmcp', arch_os, ['lib/libXdmcp.6.dylib'], '1.1.3',
      '123c77fba2179591f3c1588808f33d231e9e04d8a91c99f6684d2c7eb64626b0'
   )

   build_single_arch ('dfu-util', arch_os, ['bin/dfu-util'])
   build_single_arch ('libusb', arch_os, ['lib/libusb-1.0.0.dylib'])

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
      os.path.join (PATH_ARTIFACTS, 'toolchain_catalina.tar.gz'),
      '-C', PATH_THIS,
      'bin'
   ])


#-- build_big_sur ------------------------------------------------------------

def build_big_sur ():
   if os.path.exists (PATH_BIN):
      shutil.rmtree (PATH_BIN)
   os.makedirs (PATH_BIN)

   arch_oses = ['big_sur', 'arm64_big_sur']

   build_multi_arch ('cairo', arch_oses, ['lib/libcairo.2.dylib'])
   build_multi_arch ('libpng', arch_oses, ['lib/libpng16.16.dylib'])
   build_multi_arch ('freetype', arch_oses, ['lib/libfreetype.6.dylib'])
   build_multi_arch ('fontconfig', arch_oses, ['lib/libfontconfig.1.dylib'])
   build_multi_arch ('pixman', arch_oses, ['lib/libpixman-1.0.dylib'])
   build_multi_arch (
      'libxcb', arch_oses,
      ['lib/libxcb-shm.0.dylib', 'lib/libxcb.1.dylib', 'lib/libxcb-render.0.dylib']
   )
   build_multi_arch ('libx11', arch_oses, ['lib/libX11.6.dylib'])
   build_multi_arch ('libxext', arch_oses, ['lib/libXext.6.dylib'])
   build_multi_arch ('libxrender', arch_oses, ['lib/libXrender.1.dylib'])
   build_multi_arch ('libxau', arch_oses, ['lib/libXau.6.dylib'])
   build_multi_arch ('libxdmcp', arch_oses, ['lib/libXdmcp.6.dylib'])

   build_multi_arch ('dfu-util', arch_oses, ['bin/dfu-util'])
   build_multi_arch ('libusb', arch_oses, ['lib/libusb-1.0.0.dylib'])

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
      os.path.join (PATH_ARTIFACTS, 'toolchain_big_sur.tar.gz'),
      '-C', PATH_THIS,
      'bin'
   ])


#-- main ---------------------------------------------------------------------

def main ():
   if os.path.exists (PATH_ARTIFACTS):
      shutil.rmtree (PATH_ARTIFACTS)
   os.makedirs (PATH_ARTIFACTS)

   build_catalina ()
   build_big_sur ()



#--------------------------------------------------------------------------

if __name__ == '__main__':
   sys.exit (main ())

