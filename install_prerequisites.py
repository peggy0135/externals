#!/usr/bin/env python
from __future__ import print_function

import build
import errno
import logging
import optparse
import os
import platform
import sys

RUBY_VERSION = build.ruby_requirements['ruby']
RVM_PATH = build.ruby_requirements['path']

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

def install_rvm_and_ruby():
    cmd = 'curl -sSL https://rvm.io/mpapis.asc | sudo gpg --import -'
    build.run_cmd(cmd, unsafe_shell=True, check_rc='curl failed')
    cmd = 'curl -sSL https://rvm.io/pkuczynski.asc | sudo gpg --import -'
    build.run_cmd(cmd, unsafe_shell=True, check_rc='curl failed')
    cmd = 'curl -sSL https://get.rvm.io | sudo bash -s stable'
    build.run_cmd(cmd, unsafe_shell=True, check_rc='curl failed')
    cmd = "sudo -E su -c '{rvm_path}/rvm reload && {rvm_path}/rvm requirements run && {rvm_path}/rvm install {ruby_version}'".format(
        ruby_version = RUBY_VERSION,
        rvm_path = RVM_PATH )
    build.run_cmd(cmd, unsafe_shell=True, run_env=True, check_rc='rvm ruby install failed')

def install_fpm_gem():
    build.set_ruby_path()
    cmd = """sudo -E su -c 'PATH="{PATH}"; export PATH; {rvm_path}/rvm reload && {rvm_path}/rvm use {ruby_version} && gem install -v 1.4.0 fpm'""".format(
        ruby_version = RUBY_VERSION,
        rvm_path = RVM_PATH,
        PATH = os.environ['PATH'] )
    build.run_cmd(cmd, unsafe_shell=True, run_env=True, check_rc='fpm gem install failed')


def main():
    # configure parser
    parser = optparse.OptionParser()
    parser.add_option('-v', '--verbose', action="count", dest='verbosity', default=1, help='print more information to stdout')
    parser.add_option('-q', '--quiet', action='store_const', const=0, dest='verbosity', help='print less information to stdout')
    parser.add_option('-p', '--package', action='store_true', dest='package', default=True)
    parser.add_option('-n', '--no-package', action='store_false', dest='package')
    (options, args) = parser.parse_args()

    # configure logging
    log = logging.getLogger()
    if options.verbosity >= 2:
        log.setLevel(logging.DEBUG)
    elif options.verbosity == 1:
        log.setLevel(logging.INFO)
    else:
        log.setLevel(logging.WARNING)
    ch = logging.StreamHandler()
    formatter = logging.Formatter("%(levelname)s - %(message)s")
    ch.setFormatter(formatter)
    log.addHandler(ch)

    pld = platform.linux_distribution()[0]
    if pld == '':
        import distro
        pld = distro.linux_distribution()[0]

    if pld in ['debian', 'Ubuntu']:
        log.info('Detected: {0}'.format(pld))
        cmd = ['sudo', 'apt-get', 'update', '-y']
        build.run_cmd(cmd, check_rc='getting updates failed')
        # get prerequisites
        cmd = ['sudo','apt-get','install','-y','curl','automake','make','autoconf2.13','texinfo',
               'help2man','g++','git','lsb-release','libtool','python-dev','libbz2-dev','zlib1g-dev',
               'libcurl4-gnutls-dev','libxml2-dev','pkg-config','uuid-dev','libssl-dev', 'fuse', 'libfuse2',
               'libfuse-dev', 'libmicrohttpd-dev', 'unixodbc-dev']
        build.run_cmd(cmd, check_rc='installing prerequisites failed')
        # if old, bootstrap g++
        if pld in ['Ubuntu'] and platform.linux_distribution()[1] < '14':
            # ubuntu12 ships with g++ 4.6 - needs 4.8+ to build clang
            log.info('Detected: Old Ubuntu - need to get g++ 4.8 to build clang')
            cmd = ['sudo','apt-get','install','-y','python-software-properties']
            build.run_cmd(cmd, check_rc='installing add-apt-repository prereq failed')
            cmd = ['sudo', 'add-apt-repository', '-y', 'ppa:ubuntu-toolchain-r/test']
            build.run_cmd(cmd, check_rc='installing ppa failed')
            cmd = ['sudo', 'apt-get', 'update', '-y']
            build.run_cmd(cmd, check_rc='getting updates failed')
            cmd = ['sudo', 'apt-get', 'install', '-y', 'g++-4.8']
            build.run_cmd(cmd, check_rc='installing g++-4.8 failed')
            cmd = ['sudo', 'update-alternatives', '--install', '/usr/bin/g++', 'g++', '/usr/bin/g++-4.8', '50']
            build.run_cmd(cmd, check_rc='swapping g++-4.8 failed')
            cmd = ['sudo', 'update-alternatives', '--install', '/usr/bin/gcc', 'gcc', '/usr/bin/gcc-4.8', '50']
            build.run_cmd(cmd, check_rc='swapping gcc-4.8 failed')
        # if new, get autoconf
        if pld in ['Ubuntu'] and platform.linux_distribution()[1] > '16':
            log.info('Detected: Ubuntu 16+ - need to get autoconf')
            cmd = ['sudo','apt-get','install','-y','autoconf','rsync']
            build.run_cmd(cmd, check_rc='installing autoconf failed')
        if pld in ['Ubuntu'] and platform.linux_distribution()[1] >= '16':
            cmd = ['sudo','apt-get','install','-y','patchelf']
            build.run_cmd(cmd, check_rc='installing patchelf failed')

    elif pld in ['CentOS', 'CentOS Linux', 'Red Hat Enterprise Linux Server', 'Scientific Linux']:
        log.info('Detected: {0}'.format(pld))
        # prep
        cmd = ['sudo', 'rpm', '--rebuilddb']
        build.run_cmd(cmd, check_rc='rpm rebuild failed')
        cmd = ['sudo','yum','clean','all']
        build.run_cmd(cmd, check_rc='yum clean failed')
        #check 'centos 8' or 'rocky 8.4'
        if os.path.isfile('/etc/redhat-release'):
            if (platform.linux_distribution()[0] == 'CentOS Linux' or platform.linux_distribution()[0] == 'Rocky Linux' ) and platform.linux_distribution()[1].find('8.4') != -1:
                pass
            else:
                cmd = ['sudo','yum','install','centos-release-scl-rh', '-y']
                build.run_cmd(cmd, check_rc='yum install failed')
        cmd = ['sudo','yum','update','-y','glibc*','yum*','rpm*','python*']
        build.run_cmd(cmd, check_rc='yum update failed')
        # get prerequisites
        cmd = ['sudo','yum','install','-y','epel-release','wget','openssl','ca-certificates']
        build.run_cmd(cmd, check_rc='installing epel failed')
        #check 'centos 8' or 'rocky 8.4'
        if os.path.isfile('/etc/redhat-release'):
            if (platform.linux_distribution()[0] == 'CentOS Linux' or platform.linux_distribution()[0] == 'Rocky Linux' ) and platform.linux_distribution()[1].find('8.4') != -1:
                cmd = ['sudo','dnf','install','-y','curl','gcc-c++','git','autoconf','automake',
                        'rpm-build','rubygems','ruby-devel','zlib-devel','fuse','fuse-devel',
                        'bzip2-devel','libcurl-devel','libxml2-devel','libtool','libuuid-devel','openssl-devel','unixODBC-devel','patchelf']
                build.run_cmd(cmd, check_rc='installing prerequisites failed')
                cmd = ['dnf', '--enablerepo=powertools', '-y', 'install', 'texinfo','help2man','libmicrohttpd-devel']
                build.run_cmd(cmd, check_rc='installing prerequisites failed')
                cmd = ['sudo', 'dnf', 'install', '-y', 'python2-devel']
                build.run_cmd(cmd, check_rc='installing prerequisites failed')
                cmd = ['dnf', '-y', 'install', 'pam-devel']
                build.run_cmd(cmd, check_rc='installing prerequisites failed')
            else:
                cmd = ['sudo','yum','install','-y','curl','gcc-c++','git','autoconf','automake','texinfo',
                        'help2man','rpm-build','rubygems','ruby-devel','python-devel','zlib-devel','fuse','fuse-devel',
                        'bzip2-devel','libcurl-devel','libmicrohttpd-devel','libxml2-devel','libtool','libuuid-devel','openssl-devel','unixODBC-devel','patchelf']
                build.run_cmd(cmd, check_rc='installing prerequisites failed')

    elif pld in ['openSUSE ', 'openSUSE Leap', 'SUSE Linux Enterprise Server', 'SLES']:
        log.info('Detected: {0}'.format(pld))
        # get prerequisites
        cmd = ['sudo','zypper','install','-y','curl','tar','gzip','git','ruby-devel','libmicrohttpd-devel','makeinfo','rubygems',
               'libopenssl-devel','rpm-build','help2man','python-devel','libbz2-devel','libcurl-devel','libxml2-devel','libtool',
               'libuuid-devel','uuid-devel','unixODBC-devel','cyrus-sasl','patchelf']
        build.run_cmd(cmd, check_rc='installing prerequisites failed')
    else:
        if platform.mac_ver()[0] != '':
            log.info('Detected: {0}'.format(platform.mac_ver()[0]))
            # get prerequisites
            cmd = ['brew','install','git','help2man','texinfo','libtool']
            build.run_cmd(cmd, check_rc='installing prerequisites failed')
            cmd = ['brew','link','texinfo','--force']
            build.run_cmd(cmd, check_rc='linking texinfo failed')
        else:
            log.error('Cannot determine prerequisites for platform [{0}]'.format(pld))
            return 1

    # get necessary ruby gems
    if options.package:
        install_rvm_and_ruby()
        install_fpm_gem()


if __name__ == '__main__':
    sys.exit(main())
