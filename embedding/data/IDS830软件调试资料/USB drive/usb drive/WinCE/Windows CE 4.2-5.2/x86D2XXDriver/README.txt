Notes on INF files

INF files are for INSTALLATION ONLY. After a particular device has been installed the inf file becomes redundant and changes to the inf file will not affect the device.

By default the D2XX driver for windows CE (ftdi_d2xx.dll) will work with devices of VID and PID 0x0403 and 0x6001.

If you require a different VID and PID device to work with this driver then you can use a INF file along with the driver. The INF file format is similar to the Windows INF file - the main difference being that it is an extremely cut down version. 
On startup the driver will read the INF file (if it is present in the \Windows\ directory) and use the settings you provide. 

NOTE: YOU MUST NOT CHANGE THE GENERAL FORMAT OF THE INF FILE - DOING THIS COULD CAUSE YOUR INSTALLATION TO HALT THE DEVICE AND THEREFORE REQUIRE A REBOOT. BEFORE PERFORMING THE FOLLOWING PROCEDURE IT IS RECOMMENDED YOU BACK UP ALL ESSENTIAL DATA.


The main section you must alter in the INF file(ftdid2xx.inf - DO NOT CHANGE THIS NAME OR THE DRIVER WILL NOT RECOGNISE IT)

[FtdiHw]
"FTDI device"=FTDI,USB\&VID_0403&PID_6001

change the 4 digits after the underscore to input custom VID and PIDs. You MUST keep the length of the number to 4 digits so for example if your PID is hex 0x0023 (35 decimal) you must have the following entry in the INF file

[FtdiHw]
"FTDI device"=FTDI,USB\&VID_0403&PID_0023

The INF file does not support multiple VID and PIDs - if you want to install 2 devices with different VIDs and PIDs you must create a separate INF file for each device then copy the INF file to \Windows at the appropriate installation point.

Additional Settings 

Under the [FTDI.NT.HW.AddReg] section of the INF file you can change the inner working of the driver threads using the following sections
HKR,,"BulkPriority",0x00010001,2 - sets the priority of the reading thread of the driver Valid range 0(High priority) to 7(Low priority). Setting this value may cause your hardware to stop functioning therefore take care when setting these values and backup any data you may need.

HKR,,"InTransferSize",0x00010001,64
HKR,,"OutTransferSize",0x00010001,4096
These 2 settings adjust the bulk transfer size. If you are having problems getting the driver to work - try
setting the InTransfer size to 64 and working upwards to find a suitable value. SetUSBParamters alters the same transfer sizes.

Support for CF USB Host
A registry setting may be required to suppor CF host cards (for example the Ratoc REX-CFU1) the following registry setting should be used in this case
HKR,,"ConfigFlags",0x00010001,0x00000200(bit 1 of the second byte of the configuration flag data).

To have a device install automatically (without the need for INF files) you can use the suggested registry settings in the d2xx.reg file.

[HKEY_LOCAL_MACHINE\Drivers\USB\LoadClients\1027_24577] - your VID and PID must be reflected in this setting (1027_24577 corresponds to a VID and PID of 0x0403(1027 decimal) and 0x6001(24577 decimal)).

FT_NOTIFY_ON_UNPLUG 
Use this flag if you want to be notified on an unlug while the device is open use this flag coupled with FT_SetEventNotification (along with any the RX event and Modem Status event if required). 
