import glob
import os
import shutil
import sh

from pythonforandroid.logger import info
from pythonforandroid.recipe import CompiledComponentsPythonRecipe
from pythonforandroid.util import current_directory, ensure_dir, touch


class ReportlabRecipe(CompiledComponentsPythonRecipe):
    version = 'fe660f227cac'
    url = 'https://hg.reportlab.com/hg-public/reportlab/archive/{version}.tar.gz'
    depends = ['freetype']
    call_hostpython_via_targetpython = False

    def prebuild_arch(self, arch):
        if not self.is_patched(arch):
            super().prebuild_arch(arch)
            recipe_dir = self.get_build_dir(arch.arch)

            for subdir in ("rl_accel", "renderPM"):
                target = os.path.join(recipe_dir, "src", "rl_addons", subdir)
                if os.path.exists(target):
                    shutil.rmtree(target)
                    info("reportlab recipe: REMOVED {} C extension for Python 3.14 compat".format(subdir))

            font_dir = os.path.join(recipe_dir, "src", "reportlab", "fonts")
            if os.path.exists(font_dir):
                for file in os.listdir(font_dir):
                    if file.lower().startswith('darkgarden'):
                        os.remove(os.path.join(font_dir, file))

            self.apply_patch('patches/fix-setup.patch', arch.arch)
            touch(os.path.join(recipe_dir, '.patched'))
            ft = self.get_recipe('freetype', self.ctx)
            ft_dir = ft.get_build_dir(arch.arch)
            ft_lib_dir = os.environ.get('_FT_LIB_', os.path.join(ft_dir, 'objs', '.libs'))
            ft_inc_dir = os.environ.get('_FT_INC_', os.path.join(ft_dir, 'include'))
            tmp_dir = os.path.normpath(os.path.join(recipe_dir, "..", "..", "tmp"))
            with current_directory(recipe_dir):
                ensure_dir(tmp_dir)
                pfbfile = os.path.join(tmp_dir, "pfbfer-20070710.zip")
                if not os.path.isfile(pfbfile):
                    sh.wget("http://www.reportlab.com/ftp/pfbfer-20070710.zip", "-O", pfbfile)
                sh.unzip("-u", "-d", os.path.join(recipe_dir, "src", "reportlab", "fonts"), pfbfile)
                if os.path.isfile("setup.py"):
                    with open('setup.py', 'r') as f:
                        text = f.read().replace('_FT_LIB_', ft_lib_dir).replace('_FT_INC_', ft_inc_dir)
                    with open('setup.py', 'w') as f:
                        f.write(text)

    def is_patched(self, arch):
        recipe_dir = self.get_build_dir(arch.arch)
        return os.path.exists(os.path.join(recipe_dir, '.patched'))


    def build_compiled_components(self, arch):
        info('Building compiled components in {}'.format(self.name))
        env = self.get_recipe_env(arch)
        hostpython = sh.Command(self.hostpython_location)
        with current_directory(self.get_build_dir(arch.arch)):
            if self.install_in_hostpython:
                shprint(hostpython, 'setup.py', 'clean', '--all', _env=env)
            shprint(hostpython, 'setup.py', self.build_cmd, '-v',
                    _env=env, *self.setup_extra_args)
            # If no C extensions remain (removed for Python 3.14 compat),
            # build/lib.* won't exist. Strip only if present.
            build_dirs = glob.glob('build/lib.*')
            if build_dirs:
                shprint(sh.find, build_dirs[0], '-name', '"*.o"', '-exec',
                        env['STRIP'], '{}', ';', _env=env)
            else:
                info('reportlab recipe: no C extensions to strip')


recipe = ReportlabRecipe()
