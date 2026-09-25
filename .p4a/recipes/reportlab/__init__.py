from pythonforandroid.recipe import PythonRecipe


class ReportlabRecipe(PythonRecipe):
    version = '4.4.1'
    url = 'https://files.pythonhosted.org/packages/7b/d8/c3366bf10a5a5fcc3467eefa9504f6aa24fcda5817b5b147eabd37a385e1/reportlab-{version}.tar.gz'
    depends = ['setuptools', 'pillow']
    call_hostpython_via_targetpython = False
    # Pillow comes from its p4a recipe; --no-deps prevents pip from installing
    # a host-compatible wheel into the Android target.
    setup_extra_args = ['--no-deps']

    def get_recipe_env(self, arch=None):
        env = super().get_recipe_env(arch)
        env['NO_RL_ACCEL'] = '1'
        return env


recipe = ReportlabRecipe()
