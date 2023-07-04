import os
import requests
from setuptools import setup

with open("README.md") as readme_file:
    readme = readme_file.read()

this = os.path.dirname(os.path.realpath(__file__))


def read(name):
    with open(os.path.join(this, name)) as f:
        return f.read()

# Used for the tar.gz/snap releases
'''
# fetches release version from github
latest_release_url = f"https://api.github.com/repos/AdnanHodzic/auto-cpufreq/releases/latest"
latest_release = requests.get(latest_release_url).json()
VERSION =  latest_release["tag_name"]'''
VERSION = "1.9.8"


setup(
    name="auto-cpufreq",
    setuptools_git_versioning={
        "starting_version": VERSION,
        "template": "{tag}+{sha}",
        "dev_template": "{tag}+{sha}",
        "dirty_template": "{tag}+{sha}.post{ccount}.dirty"
    },
    setup_requires=["setuptools-git-versioning"],
    description="Automatic CPU speed & power optimizer for Linux",
    long_description=readme,
    author="Adnan Hodzic",
    author_email="adnan@hodzic.org",
    url="https://github.com/AdnanHodzic/auto-cpufreq",
    packages=["auto_cpufreq"],
    install_requires=read("requirements.txt"),
    include_package_data=True,
    zip_safe=True,
    license="GPLv3",
    keywords="linux cpu speed power frequency turbo optimzier auto cpufreq",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Operating System :: POSIX :: Linux" "Environment :: Console" "Natural Language :: English",
    ],
    scripts=["bin/auto-cpufreq"],
)
