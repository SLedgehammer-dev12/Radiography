from pythonforandroid.recipe import PythonRecipe


class KivyMDRecipe(PythonRecipe):
    version = '1.1.1'
    url = 'https://github.com/kivymd/KivyMD/archive/refs/tags/{version}.tar.gz'
    depends = ['python3', 'kivy', 'setuptools', 'pillow', 'requests']
    call_hostpython_via_targetpython = False
    # Dependencies are provided by p4a recipes (kivy is built with its own
    # recipe env); without --no-deps pip would rebuild kivy from source
    # without NDKPLATFORM and fail on missing GL/gl.h.
    setup_extra_args = ['--no-deps']


recipe = KivyMDRecipe()
