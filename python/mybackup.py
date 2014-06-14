#!/usr/bin/python
#
#
import sys
import getopt
import os
import platform
import time
import ConfigParser
import logging
import shutil
import smtplib
import getpass
import tarfile

def Usage():
    print '--------------------------------------------------------------------------'
    print 'Usage: mybackup.py [OPTIONS]                                              '
    print ' -h     Print usage                                                       '
    print ' -f     Perform full backup, plus prepare the full backup -               ' 
    print '        no binary logs are backed up                                      '
    print ' -b     Perform binary logs backup only                                   '
    print '--------------------------------------------------------------------------'    
    sys.exit(0)

if len(sys.argv) <> 2:
    Usage()

## 
mybackup_cfg = './mybackup.cfg'
config = ConfigParser.ConfigParser()
if config.read(mybackup_cfg):
   try:
      username = config.get('access', 'user')
      password = config.get('access', 'password')
      backup_retention = float(config.get('backup', 'retention'))
      use_memory_size = config.get('xtrabackup', 'use_memory_size')
      mailto = config.get('notification', 'mailto')
      tmp_destn = config.get('location', 'tmp_destn')
      backup_destn = config.get('location', 'backup_destn')
      binlog_destn = config.get('location', 'binlog_destn')

      cwd = os.getcwd()
      tstamp = time.strftime('%Y%m%d_%H%M%S')
      dstamp = time.strftime('%Y%m%d')
   except ConfigParser.Error:
      print "Error parsing %s", mybackup_cfg
      raise
else:
   print "cannot run; config file mybackup.cfg is not present ..."
   sys.exit(1) 


## check if the same process is already running
def am_i_already_running():
   global pidfile
   pid = str(os.getpid())
   pidfile = '/tmp/mybackup_' +bkp_type +'.pidfile'
   if os.path.isfile(pidfile):
      print "%s already exists, exiting" % pidfile
      logging.info('mybackup_' + bkp_type + ' already running...')
      logging.info(pidfile + ' already exists, exiting :( ')
      msg1 = 'Please check log: '+ logfile
      sendemail(platform.node()+': mybackup_' + bkp_type + ' already running...', msg1, '')
      sys.exit(1)
   else:
      file(pidfile, 'w').write(pid)
      logging.info('creating pidfile %s for this run ...' % pidfile)

##
def setup_var():

   global backupdir
   global logdir
   global logfile
   global restorefile

   if bkp_type == 'f':
      backupdir = backup_destn.rstrip('//') + '/' + tstamp
      logdir = backupdir + '_log'
      logfile = logdir + '/' + 'mybackup_f.log.' + tstamp
      restorefile = logdir + '/' +  'mybackup_f.restore.' + tstamp
   if bkp_type == 'b':
      backupdir = binlog_destn.rstrip('//') + '/' + dstamp
      logdir = backupdir + '_log'
      logfile = logdir + '/' + 'mybackup_b.log.' + dstamp

##
def end(status):
   logging.info('mybackup.py run completed with status: '+ status)
   if bkp_type == 'f':
      os.rename(logfile, logfile+'.'+status)
      msg1 = 'Please check log: '+ logfile+'.'+status
   if bkp_type == 'b':
      msg1 = 'Please check log: '+ logfile
   if status != 'OK':
      sendemail(platform.node()+': mybackup.py run completed with status: '+status, msg1, '')

   os.unlink(pidfile)

##
def setup_dir():
   if bkp_type == 'f':
      if not os.path.exists(backup_destn):
         os.makedirs(backup_destn)
      if not os.path.exists(logdir):
         os.makedirs(logdir)
   if bkp_type == 'b':
      if not os.path.exists(binlog_destn):
         os.makedirs(binlog_destn)
      if not os.path.exists(logdir):
         os.makedirs(logdir)
   logging.basicConfig(filename=logfile, level=logging.DEBUG, format='%(asctime)s:%(levelname)s:%(message)s', datefmt='%y%m%d %H:%M:%S')

## Perform full backup, plus prepare the full backup - no binary logs are backed up
def full_backup():
 #Full Backup
 try:
   logging.info('starting mybackup.py run for full backup ...')

   os.system('mysql --user=' +username +' --password=' +password + ' ' + "-e'FLUSH LOGS'")

   time.sleep(5)

   full_bkp_cmd = 'innobackupex --user=' +username +' --password=' +password + ' --rsync --tmpdir=' + tmp_destn + ' ' +  backupdir + ' --no-timestamp >> ' +logfile +' 2>&1 '

   logging.info('running the following command ...')
   logging.info(full_bkp_cmd)

   retcode = os.system(full_bkp_cmd)
   if retcode == 0:
      logging.info('full backup completed successfully!')
   else:
      logging.error('full backup failed ...')
      raise

   # Prepare the backup for restore
   logging.info('preparing full backup for restore ...')

   prep_bkp_cmd = 'innobackupex --user=' +username +' --password=' +password + ' --apply-log --use-memory=' +use_memory_size + ' --tmpdir=' + tmp_destn + ' ' +  backupdir +'>> ' +logfile +' 2>&1 '

   logging.info('running the following command ...')
   logging.info(prep_bkp_cmd)

   #Prepare Backup for Restore
   retcode = os.system(prep_bkp_cmd)
   if retcode == 0:
      logging.info('preparing full backup for restore completed successfully!')
   else:
      logging.error('preparing full backup for restore failed ...')
      raise

   #Generate restore file for this backup
   logging.info('creating restore commands file ...')

   restore_bkp_cmd = 'innobackupex --copy-back ' + backupdir + "/full_backup"

   f = open(restorefile, "w")
   f.write("Steps to restore this backup:\n")
   f.write("-----------------------------\n")
   f.write("0. gunzip/untar the .tar.gz file in full_backup directory: tar zxvf <>.tar.gz\n")
   f.write("1. Make sure mysql is shutdown before you start the restore: service mysql stop\n")
   f.write("2. Make sure the datadir is empty before you start the restore: cd <datadir>; rm -rf *\n")
   f.write("3. Execute the following restore command after steps 1 and 2 are complete:\n")
   f.write(restore_bkp_cmd + "\n")
   f.write("4. After step 3, check the contents of datadir, if they are owned by root make sure they belong to mysql:mysql by running the below command\n")
   f.write("   chown -R mysql:mysql <datadir>\n")
   f.write("5. Start mysql server: service mysql start\n")
   f.write("6. Roll forward the db to curent state by applying bin logs using below steps:\n")
   f.write("  "+ cwd +"/run_binlog.sh " + backupdir + "/full_backup/xtrabackup_binlog_info\n")
   f.write("   and then follow instructions from executing run_binlog.sh\n")
   f.close()
   logging.info('restore commands file ' + restorefile + ' has been generated, use the contents of this file to restore this backup')

 except:
   end('ERROR')
   raise

## Perform binary logs backup only
def binlog_backup():

 try:
   #Backup binary logs
   logging.info('starting mybackup.py run for bin logs ...')

   ostype = platform.system()
   osdist = platform.dist()

   if (ostype.upper() == 'LINUX') and (osdist[0].upper() == 'UBUNTU'):
      mycnf = '/etc/mysql/my.cnf'
   elif (ostype.upper() == 'LINUX') and (osdist[0].upper() == 'CENTOS'):
      mycnf = '/etc/my.cnf'
   else:
      mycnf = '/etc/my.cnf'

   logging.info('my.cnf is at '+ mycnf)

   for line in open(mycnf):
      if "log-bin" in line.lower():
         binlog_location = line.split("=")[-1]

   binlog_dir = os.path.dirname(binlog_location)
   binlog_dir = binlog_dir.rstrip('//') + '/'

   logging.info('log_bin location is ' + binlog_dir)

   rsync_cmd = 'rsync -avr ' + binlog_dir + ' ' + binlog_destn + ' >> ' +logfile +' 2>&1 '

   logging.info('running the following command ...')
   logging.info(rsync_cmd)

   retcode = os.system(rsync_cmd)
   if retcode == 0:
      logging.info('backup of bin logs completed successfully!')
   else:
      logging.error('backup of bin logs failed ...')
      raise
 except:
   end('ERROR')
   raise

##Compress the backup
def compress_backup():
   try:
      logging.info('running compress full backup ...')
      gztar = tarfile.open(backupdir +".tar.gz", "w:gz")
      gztar.add(backupdir, arcname="full_backup")
      gztar.close()

      #remove the backup dir since we have gzipped tar of the backup now
      shutil.rmtree(backupdir)
      os.makedirs(backupdir)
      shutil.move(backupdir+".tar.gz" , backupdir)
      logging.info('full backup compressed succesfully ...')

   except:
      logging.error('Error with compressing full backup ...')
      end('ERROR')
      raise

##Purge old backups
def purge_old_backups(dir, age):
   try:
      for f in os.listdir(dir):
         if tstamp not in f:
            logging.info('purging backups older than '+str(backup_retention) +' days ...')
            now = time.time()
            filepath = os.path.join(dir, f)
            modified = os.stat(filepath).st_mtime
            if modified < now - age:
               logging.info('purging old backup '+filepath +' ...')
               if os.path.isfile(filepath):
                  os.remove(filepath)
               if os.path.isdir(filepath):
                  shutil.rmtree(filepath)
            else:
               logging.info(filepath +' does not meet purge criteria ...')
   except:
      logging.error('error with purging old backup ...')
      end('ERROR')
      raise

try:
    optlist, list = getopt.getopt(sys.argv[1:],':fbh:')
except getopt.GetoptError:
    Usage()
    sys.exit(1)


def sendemail(sub, msg1, msg2):
   SENDMAIL = "sendmail" # sendmail location
   p = os.popen("%s -t" % SENDMAIL, "w")
   p.write("From: DL@mycompany.com\n")
   p.write("To: " + mailto + "\n")
   p.write("Subject: "+sub+"\n")
   p.write("\n") # blank line separating headers from body
   p.write(msg1)
   p.write(msg2)
   sts = p.close()
#   if sts != 0:
#      print "Sendmail exit status", sts


############################################################################
##main
############################################################################
for opt in optlist:
    if opt[0] == '-h':
        Usage()
    if opt[0] == '-f':
        bkp_type = 'f'
        setup_var()
	setup_dir()
        am_i_already_running()
	full_backup()
        #compress_backup()
	purge_old_backups(backup_destn, (backup_retention*24*60*60))
	end('OK')
    if opt[0] == '-b':
        bkp_type = 'b'
        setup_var()
	setup_dir()
        am_i_already_running()
	binlog_backup()
	purge_old_backups(binlog_destn, ((backup_retention+2)*24*60*60))
	end('OK')
