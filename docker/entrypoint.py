import json
import logging
import os
import re
import shutil
import sys
from glob import glob

import git
import gnupg
from debian.debfile import DebFile
# from docker.key import detectPublicKey, importPrivateKey
from key import detectPublicKey, importPrivateKey

verbose = os.environ.get('INPUT_VERBOSE', False)
dry_run = os.environ.get('INPUT_DRY_RUN', False)

if verbose:
    logging.basicConfig(format='%(levelname)s: %(message)s',
                        level=logging.DEBUG)
else:
    logging.basicConfig(
        format='%(levelname)s: %(message)s', level=logging.INFO)

if __name__ == '__main__':
    logging.info('-- Parsing input --')

    repository = os.environ.get('GITHUB_REPOSITORY')

    token = os.environ.get('INPUT_TOKEN')
    branch = os.environ.get('INPUT_BRANCH', 'gh-pages')
    folder = os.environ.get('INPUT_FOLDER', 'repo')

    # platforms = os.environ.get('INPUT_PLATFORMS')
    package_arch = os.environ.get('INPUT_PLATFORM')
    # targets = os.environ.get('INPUT_TARGETS')
    package_target = os.environ.get('INPUT_TARGET')
    # packages = os.environ.get('INPUT_PACKAGES')
    package_path = os.environ.get('INPUT_PACKAGE')
    # versions = os.environ.get('INPUT_VERSIONS')
    package_version = os.environ.get('INPUT_VERSION')

    if None in (token, package_arch, package_target, package_path, package_version):
        logging.error('Required key is missing')
        sys.exit(1)

    deb_file_path = package_path.strip()
    deb_file_version = package_version.strip()

    # platforms_list = json.loads(platforms)
    # targets_list = json.loads(targets)
    # packages_list = json.loads(packages)
    # versions_list = json.loads(versions)

    logging.debug(package_arch)
    logging.debug(package_version)
    logging.debug(deb_file_path)
    logging.debug(deb_file_version)

    # FIXME: This whole "file version" logic seems fairly dumb and useless, no?
    # if deb_file_version not in supported_version_list:
    #     logging.error(
    #         'File version target is not listed in repo supported version list')
    #     sys.exit(1)

    public_key = os.environ.get('INPUT_PUBLIC_KEY')
    private_key = os.environ.get('INPUT_PRIVATE_KEY')
    private_key_passphrase = os.environ.get('INPUT_PRIVATE_KEY_PASSPHRASE')

    # logging.debug(token)
    # logging.debug(platforms_list)
    # logging.debug(targets_list)

    logging.info('-- Done parsing input --')

    # Clone repo

    logging.info('-- Cloning current Github page --')

    github_user = repository.split('/')[0]
    github_slug = repository.split('/')[1]

    if os.path.exists(github_slug):
        shutil.rmtree(github_slug)

    git_working_folder = github_slug + "-" + branch
    if os.path.exists(git_working_folder):
        shutil.rmtree(git_working_folder)

    git_repo = git.Repo.clone_from(
        'https://x-access-token:{}@github.com/{}.git'.format(
            token, repository),
        git_working_folder,
    )

    git_refs = git_repo.remotes.origin.refs
    git_refs_name = list(map(lambda x: str(x).split('/')[-1], git_refs))

    logging.debug(git_refs_name)

    if branch not in git_refs_name:
        git_repo.git.checkout(b=branch)
    else:
        git_repo.git.checkout(branch)

    # Generate metadata
    logging.debug("cwd : {}".format(os.getcwd()))
    logging.debug(os.listdir())

    deb_file_handle = DebFile(filename=glob(package_path)[0])
    deb_file_control = deb_file_handle.debcontrol()

    current_metadata = {
        'format_version': 1,
        'sw_version': deb_file_control['Version'],
        'sw_architecture': deb_file_control['Architecture'],
        'linux_version': deb_file_version
    }

    current_metadata_str = json.dumps(current_metadata)
    logging.debug('Metadata {}'.format(current_metadata_str))

    # Get metadata
    all_commit = git_repo.iter_commits(branch)
    all_apt_action_commit = list(
        filter(lambda x: (x.message[:12] == '[apt-action]'), all_commit))
    apt_action_metadata_str = list(
        map(
            lambda x: re.findall('apt-action-metadata({.+})$', x.message),
            all_apt_action_commit,
        )
    )
    apt_action_valid_metadata_str = list(
        filter(lambda x: len(x) > 0, apt_action_metadata_str))
    apt_action_metadata = list(
        map(lambda x: json.loads(x[0]), apt_action_valid_metadata_str))

    logging.debug(all_apt_action_commit)
    logging.debug(apt_action_valid_metadata_str)

    for check_metadata in apt_action_metadata:
        if (check_metadata == current_metadata):
            logging.info(
                'This version of this package has already been added to the repo, skipping it')
            sys.exit(0)

    logging.info('-- Done cloning current Github page --')

    # Prepare key

    logging.info('-- Importing key --')

    key_file = os.path.join(git_working_folder, 'public.key')
    gpg = gnupg.GPG()

    detectPublicKey(gpg, key_file, public_key)
    private_key_id = importPrivateKey(gpg, private_key)

    logging.info('-- Done importing key --')

    # Prepare repo

    logging.info('-- Preparing repo directory --')

    apt_dir = os.path.join(git_working_folder, folder)
    apt_conf_dir = os.path.join(apt_dir, 'conf')

    if not os.path.isdir(apt_dir):
        logging.info('Existing repo not detected, creating new repo')
        os.mkdir(apt_dir)
        os.mkdir(apt_conf_dir)

    logging.debug('Creating repo config')

    with open(os.path.join(apt_conf_dir, 'distributions'), 'w') as distributions_file:
        # for codename in targets_list:
        distributions_file.write('Description: {}\n'.format(repository))
        distributions_file.write('Codename: {}\n'.format(package_target))
        distributions_file.write(
            'Architectures: {}\n'.format(package_arch))
        distributions_file.write('Components: main\n')
        distributions_file.write('SignWith: {}\n'.format(private_key_id))
        distributions_file.write('\n\n')

    logging.info('-- Done preparing repo directory --')

    # Fill repo

    logging.info('-- Adding package to repo --')

    logging.info('Adding {}'.format(deb_file_path))
    reprepro_includedeb_cmd = 'reprepro -b {} --export=silent-never includedeb {} {}'.format(
        apt_dir,
        deb_file_version,
        deb_file_path,
    )
    reprepro_includedeb_exit = os.WEXITSTATUS(
        os.system(reprepro_includedeb_cmd))
    if (reprepro_includedeb_exit != 0):
        logging.error('Command {} failed with {}'.format(
            reprepro_includedeb_cmd, reprepro_includedeb_exit))
        sys.exit(reprepro_includedeb_exit)

    logging.debug('Signing to unlock key on gpg agent')
    gpg.sign('test', keyid=private_key_id, passphrase=private_key_passphrase)

    logging.debug('Export and sign repo')
    reprepro_export_cmd = 'reprepro -b {} export'.format(apt_dir)
    reprepro_export_exit = os.WEXITSTATUS(os.system(reprepro_export_cmd))
    if (reprepro_export_exit != 0):
        logging.error('Command {} failed with {}'.format(
            reprepro_export_cmd, reprepro_export_exit))
        sys.exit(reprepro_export_exit)

    logging.info('-- Done adding package to repo --')

    # Commiting and push changes
    logging.info('-- Saving changes --')

    # Only push changes if dry run is not enabled
    if not dry_run:
        git_repo.config_writer().set_value(
            'user', 'email', '{}@users.noreply.github.com'.format(github_user)
        )

        git_repo.git.add('*')
        git_repo.index.commit(
            '[apt-action] Update apt repo\n\n\napt-action-metadata{}'.format(
                current_metadata_str)
        )
        git_repo.git.push('--set-upstream', 'origin', branch)
    else:
        logging.info('-- Dry-run mode, not actually saving any changes --')

    # Append "url=foo" to GITHUB_OUTPUT environment variable (do not use "set-output" as that is deprecated)
    # In a shell script, we would do this like so: echo "{name}={value}" >> $GITHUB_OUTPUT
    url = 'foo'
    with open(os.environ['GITHUB_OUTPUT'], 'a') as fh:
        print(f'url={url}', file=fh)

    logging.info('-- Done saving changes --')
