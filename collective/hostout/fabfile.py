import os
import os.path
from fabric import api, contrib

def _createuser(buildout_user='buildout'):
    """Creates a user account to run the buildout in"""
    #keyname="buildout_dsa.%s"%(buildout_host)
    #if not os.path.exists(keyname):
    if True:
        sudo('test -d ~$(buildout_user) || adduser $(buildout_user)')
        sudo('test -d ~$(buildout_user)/.ssh || mkdir ~$(buildout_user)/.ssh;')
        sudo('(chmod 700 ~$(buildout_user)/.ssh; touch ~$(buildout_user)/.ssh/authorized_keys)')
        sudo('chmod 600 ~$(buildout_user)/.ssh/authorized_keys')
        #run("rm -f /tmp/buildout_dsa")
        #run("ssh-keygen -t dsa -N '' -f /tmp/buildout_dsa")
        #run('rm ~$(buildout_user)/.ssh/buildout_dsa.pub')
        #try:
        #    download('/tmp/buildout_dsa','buildout_dsa')
        #    download('/tmp/buildout_dsa.pub','buildout_dsa.pub')
        #except:
        #    pass
        sudo('cp ~$(buildout_user)/.ssh/authorized_keys ~$(buildout_user)/.ssh/authorized_keys.bak')
        sudo('cat /tmp/buildout_dsa.pub >> ~$(buildout_user)/.ssh/authorized_keys')
    set(fab_key_filename=keyname)


def setaccess():

    #Copy authorized keys to plone user:
    key_filename, key = api.env.hostout.getIdentityKey()
    #api.sudo("rm -rf ~%(owner)s/.ssh" % locals())
    for owner in [api.env.user, api.env['buildout-user']]:
        api.sudo("mkdir -p ~%(owner)s/.ssh" % locals())
        api.sudo('touch ~%(owner)s/.ssh/authorized_keys'%locals() )
        contrib.files.append(key, '~%(owner)s/.ssh/authorized_keys'%locals(), use_sudo=True)
        #    api.sudo("echo '%(key)s' > ~%(owner)s/.ssh/authorized_keys" % locals())
        api.sudo("chown -R %(owner)s ~%(owner)s/.ssh" % locals() )
    

def setowners():   
    hostout = api.env.get('hostout')
    owner = api.env['user']
    buildout = api.env['buildout-user']
    effective = api.env['effective-user']
    path = api.env.path
    dl = hostout.getDownloadCache()
    dist = os.path.join(dl, 'dist')
    bc = hostout.getEggCache()
    var = os.path.join(path, 'var')
    
    # What we want is for
    # - login user to own the buildout and the cache.
    # - effective user to be own the var dir + able to read buildout and cache.
    
    api.sudo('chown -R %(buildout)s:%(buildout)s %(path)s && '
             ' chmod -R u+rw,g+r-w,o-rw %(path)s' % locals())
    api.sudo('mkdir -p %(var)s && chown -R %(effective)s:%(owner)s %(var)s && '
             ' chmod -R u+rw,g+wr,o-rw %(var)s ' % locals())
    
    for cache in [dist,dl,bc]:
        #HACK Have to deal with a shared cache. maybe need some kind of group
        api.sudo('mkdir -p %(cache)s && chown -R %(buildout)s:%(buildout)s %(cache)s && '
                 ' chmod -R u+rw,a+r %(cache)s ' % locals())


def initcommand(cmd):
    if cmd in ['uploadeggs','uploadbuildout','buildout','run']:
        api.env.user = api.env['buildout-user']
    else:
        api.env.user = api.env.hostout.options['user']
    key_filename = api.env['identity-file']
    if os.path.exists(key_filename):
        api.env.key_filename = key_filename
    

def predeploy():
    """Perform any initial plugin tasks. Call bootstrap if needed"""

    #run('export http_proxy=localhost:8123') # TODO get this from setting
    
    hostout = api.env['hostout']
    if not contrib.files.exists(api.env.path, use_sudo=True):
        raise Exception("Generic bootstrap unimplemented. Look for plugins")
        #bootstrap()

    api.env.cwd = api.env.path
    for cmd in hostout.getPreCommands():
        api.sudo('sh -c "%s"'%cmd)

    #Login as user plone
#    api.env['user'] = api.env['effective-user']

def bootstrap():
    """Install python,users and buildout"""
    hostout = api.env['hostout']

#    effectiveuser=hostout.effective_user
#    buildout_dir=hostout.remote_dir
#    install_dir=os.path.split(hostout.remote_dir)[0]
#    instance=os.path.split(hostout.remote_dir)[1]
#    download_cache=hostout.getDownloadCache()


    unified='Plone-3.2.1r3-UnifiedInstaller'
    unified_url='http://launchpad.net/plone/3.2/3.2.1/+download/Plone-3.2.1r3-UnifiedInstaller.tgz'

    sudo('mkdir -p %(dc)s/dist && sudo chmod -R a+rw  %(dc)s'%dict(dc=api.env.download_cache) )
    sudo(('mkdir -p %(dc)s && sudo chmod -R a+rw  %(dc)s') % dict(dc=hostout.getEggCache()) )

    #install prerequsites
    #sudo('which g++ || (sudo apt-get -ym update && sudo apt-get install -ym build-essential libssl-dev libreadline5-dev) || echo "not ubuntu"')

    #Download the unified installer if we don't have it
    buildout_dir=api.env.path
    sudo('test -f %(buildout_dir)s/bin/buildout || '
         'test -f %(dist_dir)s/%(unified)s.tgz || '
         '( cd /tmp && '
         'wget  --continue %(unified_url)s '
         '&& sudo mv /tmp/%(unified)s.tgz %(dist_dir)s/%(unified)s.tgz '
#         '&& sudo chown %(effectiveuser)s %(dist_dir)s/%(unified)s.tgz '+
        ')' % locals() )
         
    # untar and run unified installer
    sudo('test -f $(buildout_dir)/bin/buildout || '+
          '(cd /tmp && '+
          'tar -xvf $(dist_dir)/$(unified).tgz && '+
          'test -d /tmp/$(unified) && '+
          'cd /tmp/$(unified) && '+
          'sudo mkdir -p  $(install_dir) && '+
          'sudo ./install.sh --target=$(install_dir) --instance=$(instance) --user=$(effectiveuser) --nobuildout standalone && '+
          'sudo chown -R $(effectiveuser) $(install_dir)/$(instance))'
          )



def uploadeggs():
    """Release developer eggs and send to host """
    
    hostout = api.env['hostout']

    #need to send package. cycledown servers, install it, run buildout, cycle up servers

    dl = hostout.getDownloadCache()
    contents = api.run('ls %(dl)s/dist'%locals()).split()
    buildout = api.env['buildout-user']

    for pkg in hostout.localEggs():
        name = os.path.basename(pkg)
        if name not in contents:
            tmp = os.path.join('/tmp', name)
            tgt = os.path.join(dl, 'dist', name)
            api.put(pkg, tmp)
            api.run("mv -f %(tmp)s %(tgt)s && "
                    "chown %(buildout)s:%(buildout)s %(tgt)s && "
                    "chmod a+r %(tgt)s" % locals() )

def uploadbuildout():
    """Upload buildout pinned version of buildouts to host """
    hostout = api.env.hostout
    buildout = api.env['buildout-user']

    package = hostout.getHostoutPackage()
    tmp = os.path.join('/tmp', os.path.basename(package))
    tgt = os.path.join(hostout.getDownloadCache(), 'dist', os.path.basename(package))

    #api.env.warn_only = True
    if api.run("test -f %(tgt)s || echo 'None'" %locals()) == 'None' :
        api.put(package, tmp)
        api.run("mv %(tmp)s %(tgt)s" % locals() )
        #sudo('chown $(effectiveuser) %s' % tgt)


    effectiveuser=hostout.effective_user
    install_dir=hostout.remote_dir
    api.run('tar --no-same-permissions --no-same-owner --overwrite '
         '--owner %(effectiveuser)s -xvf %(tgt)s '
         '--directory=%(install_dir)s' % locals())
    

def buildout():
    """Run the buildout on the remote server """

    hostout = api.env.hostout
    hostout_file=hostout.getHostoutFile()
    #api.env.user = api.env['effective-user']
    api.env.cwd = hostout.remote_dir
    api.run('bin/buildout -c %(hostout_file)s' % locals())
    #api.sudo('sudo -u $(effectiveuser) sh -c "export HOME=~$(effectiveuser) && cd $(install_dir) && bin/buildout -c $(hostout_file)"')

#    sudo('chmod 600 .installed.cfg')
#    sudo('find $(install_dir)  -type d -name var -exec chown -R $(effectiveuser) \{\} \;')
#    sudo('find $(install_dir)  -type d -name LC_MESSAGES -exec chown -R $(effectiveuser) \{\} \;')
#    sudo('find $(install_dir)  -name runzope -exec chown $(effectiveuser) \{\} \;')



def postdeploy():
    """Perform any final plugin tasks """
    
    hostout = api.env.get('hostout')
 
    api.env.cwd = api.env.path
    for cmd in hostout.getPostCommands():
        api.sudo('sh -c "%s"'%cmd)

def run(*cmd):
    """Execute cmd on remote as login user """
    api.env.cwd = api.env.path
    api.run(' '.join(cmd))

def sudo(*cmd):
    """Execute cmd on remote as root user """
    api.env.cwd = api.env.path
    api.sudo(' '.join(cmd))

