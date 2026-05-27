using System.Linq;
using FTDI.D2xx.WinRT;
using FTDI.D2xx.WinRT.Device;
using FTDI.D2xx.WinRT.Device.EEPROM;
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Threading;
using System.Threading.Tasks;
using Windows.Foundation;
using Windows.Storage;
using Windows.System.Threading;
using Windows.UI.Core;
using Windows.UI.Xaml;
using Windows.UI.Xaml.Controls;
using Windows.UI.Xaml.Media;
using Windows.ApplicationModel;
using Windows.ApplicationModel.Activation;



namespace TestApp
{
    /// <summary>
    /// An empty page that can be used on its own or navigated to within a Frame.
    /// </summary>
    public sealed partial class MainPage : Page
    {
        private FTManager ftManager;
        private IFTDevice myDevice = null;
        private CancellationTokenSource cancellationTokenSource = new CancellationTokenSource();
        private StorageFile file = null;

        public static Windows.UI.Core.CoreDispatcher Dispatcher;

        private enum ERROR_CODES
        {
            SUCCESS = 0,
            NO_DEVICES_FOUND,
            FAILED_TO_OPEN,
            FAILED_TO_READ_ALL_DATA,
            DATA_INTEGRITY,
            GENERAL_ERROR = 0xff,
        };

        public MainPage()
        {
            this.InitializeComponent(); 
            ftManager = new FTManager();
            App.Current.Suspending += OnSuspending;
            App.Current.Resuming += OnResuming; 
        }

        private FTManager InitializeDriver()
        {
#if CUSTOM_VID_PID
            bool result = FTManager.AddVIDPID(0x1234, 0x4321);
            result = FTManager.RemoveVIDPID(0x0403, 0x6001);
            result = FTManager.RemoveVIDPID(0x0403, 0x6010);
            result = FTManager.RemoveVIDPID(0x0403, 0x6011);
            result = FTManager.RemoveVIDPID(0x0403, 0x6014);
            result = FTManager.RemoveVIDPID(0x0403, 0x6015);
#endif
            return new FTManager();
        }

        private StorageFile CreateCSV()
        {
            try
            {
                DateTime now = DateTime.Now;
                string filename = String.Format("{0}{1}{2}_WinRT.log", now.Year, now.Month, now.Day);
                StorageFolder folder = KnownFolders.DocumentsLibrary;
                var file = folder.CreateFileAsync(filename, CreationCollisionOption.OpenIfExists).AsTask();
                return file.Result;
            }
            catch
            {
                return null;
            }
        }

        private String ErrorCodeToString(ERROR_CODES code)
        {
            switch (code)
            {
                case ERROR_CODES.SUCCESS:
                    return "Success";
                case ERROR_CODES.NO_DEVICES_FOUND:
                    return "No devices attached to system";
                case ERROR_CODES.FAILED_TO_OPEN:
                    return "Open failed";
                case ERROR_CODES.FAILED_TO_READ_ALL_DATA:
                    return "Failed to read all the data";
                case ERROR_CODES.DATA_INTEGRITY:
                    return "Data read does not match data written!!!";
                default:
                    return "General error";
            }
        }

        private async Task SetUARTSettings(IFTDevice ftDevice)
        {
            UInt32 baudRate = 3000000;
            // Get the baud rate from the combo box.
            
            /*await Dispatcher.RunAsync(CoreDispatcherPriority.Normal, () =>
            {
                ComboBoxItem br = (ComboBoxItem)cbBaudRate.SelectedItem;
                baudRate = Convert.ToUInt32(br.Content);
            });*/

            /*await MainPage.Dispatcher.RunAsync(CoreDispatcherPriority.Normal, () =>
            {
                ComboBoxItem br = (ComboBoxItem)cbBaudRate.SelectedItem;
                baudRate = Convert.ToUInt32(br.Content);
            });*/

            await ftDevice.SetBaudRateAsync(baudRate);
            await ftDevice.SetFlowControlAsync(FLOW_CONTROL.RTS_CTS, 0x00, 0x00);
            await ftDevice.SetDataCharacteristicsAsync(WORD_LENGTH.BITS_8, STOP_BITS.BITS_1, PARITY.NONE);
        }

        /// <summary>
        /// This test open and closes the handle to the FTDI device 100 times.
        /// </summary>
#if DAVE        
        public async Task<Boolean> OpenCloseTest(FTManager ftManager, String deviceID)
        {
            try
            {
                int errorCode = (int) ERROR_CODES.SUCCESS;

                double start = DateTime.Now.TimeOfDay.TotalSeconds;
                String s = "\r\n\r\nStarted OpenCloseTest\r\n";
                AppendLogFile(s);
                AppendConsole(s);

                var res = await Task<Boolean>.Factory.StartNew(async (source) =>
                {
                    for (int i = 0; i < 100; i++)
                    {
                        var devList = ftManager.GetDeviceList();
                        if (devList.Count == 0)
                        {
                            errorCode = (int)ERROR_CODES.NO_DEVICES_FOUND;
                            return false;
                        }
                        
                        IFTDevice dev = ftManager.OpenByDeviceID(deviceID);
                        if (dev == null)
                        {
                            errorCode = (int)ERROR_CODES.FAILED_TO_OPEN;
                            return false;
                        }

                        await SetUARTSettings(dev);

                        dev.Close();
                    }

                    return true;
                }, WorkItemPriority.Normal);

                double finish = DateTime.Now.TimeOfDay.TotalSeconds;
                s = String.Format(
                            @"Finished OpenCloseTest:
                                Result: {0}
                                ErrorCode: {1}
                                Duration: {2}secs",
                                res,
                                errorCode,
                                Math.Round(finish - start, 2));
                AppendLogFile(s);
                AppendConsole(s);

                return res;
            }
            catch
            {
                return false;
            }
        }
#endif

        public async Task<Boolean> OpenCloseLoopbackTest(FTManager ftManager, String deviceID)
        {
            try
            {
                int errorCode = (int) ERROR_CODES.SUCCESS;

                double start = DateTime.Now.TimeOfDay.TotalSeconds;
                String s = "\r\n\r\nStarted OpenCloseLoopbackTest\r\n";
                AppendLogFile(s);
                AppendConsole(s);
                
                Boolean res = await Task.Run<Boolean>(async () =>
                {
                    for (int i = 0; i < 100; i++)
                    {
                        byte[] dataTx = new byte[10];
                        byte[] dataRx = new byte[10];

                        // Create device list...
                        var devList = ftManager.GetDeviceList();
                        if (devList.Count == 0)
                        {
                            errorCode = (int)ERROR_CODES.NO_DEVICES_FOUND;
                        }

                        // Find device in the list again...
                        IFTDevice dev = ftManager.OpenByDeviceID(deviceID);
                        if (dev == null)
                        {
                            errorCode = (int)ERROR_CODES.FAILED_TO_OPEN;
                        }

                        await SetUARTSettings(dev);

                        // Generate some random data...
                        Random rnd = new Random();
                        for (int j = 0; j < dataTx.Length; j++)
                        {
                            dataTx[j] = (byte)rnd.Next(0, 0xff);
                        }

                        dev.Close();

                        await dev.ResetAsync();
                                                
                        // Write then read back the data...
                        await dev.WriteAsync(dataTx, (uint)dataTx.Length);

                        uint count = await dev.ReadAsync(dataRx, (uint)dataTx.Length);
                        if (count < dataTx.Length)
                        {
                            errorCode = (int)ERROR_CODES.FAILED_TO_READ_ALL_DATA;
                            dev.Close();
                            return false;
                        }

                        for (int j = 0; j < dataTx.Length; j++)
                        {
                            if (dataTx[j] != dataRx[j])
                            {
                                errorCode = (int)ERROR_CODES.DATA_INTEGRITY;
                                return false;
                            }
                        }

                        dev.Close();
                    }

                    return true;
                }).AsAsyncOperation();

                double finish = DateTime.Now.TimeOfDay.TotalSeconds;
                s = String.Format(
                            @"Finished OpenCloseLoopbackTest:
                                Result: {0}
                                ErrorCode: {1}
                                Duration: {2}secs",
                                res.ToString().ToLower(),
                                errorCode,
                                Math.Round(finish - start, 2));
                AppendLogFile(s);
                AppendConsole(s);

                return res;
            }
            catch
            {
                return false;
            }
        }

        /// <summary>
        /// Loopback test that transmits 1MB of data to the device and reads it back.
        /// </summary>
        public async Task<Boolean> LoopbackTest(FTManager ftManager, String deviceID)
        {
            try
            {
                String s = "";
                double start = 0;
                int errorCode = (int) ERROR_CODES.SUCCESS;
                int TOTAL_BYTES = 65535;
                int PACKET_SIZE = 1024;
                int iterations = TOTAL_BYTES / PACKET_SIZE;
                
                Boolean res = await Task.Run<Boolean>(async () =>
                {
                    byte[] dataTx = new byte[TOTAL_BYTES];
                    byte[] dataRx = new byte[PACKET_SIZE];

                    // Generate some random data...
                    Random rnd = new Random();
                    for (int j = 0; j < dataTx.Length; j++)
                    {
                        dataTx[j] = (byte)rnd.Next(0, 0xff);
                    }

                    // Create device list...
                    var devList = ftManager.GetDeviceList();
                    if (devList.Count == 0)
                    {
                        errorCode = (int)ERROR_CODES.NO_DEVICES_FOUND;
                    }

                    // Find device in the list again...
                    IFTDevice dev = ftManager.OpenByDeviceID(deviceID);
                    if (dev == null)
                    {
                        errorCode = (int)ERROR_CODES.FAILED_TO_OPEN;
                    }

                    await SetUARTSettings(dev);

                    start = DateTime.Now.TimeOfDay.TotalSeconds;
                    s = "\r\n\r\nStarted LoopbackTest\r\n";
                    AppendLogFile(s);
                    AppendConsole(s);

                    for (int i = 0; i < iterations; i++)
                    {
                        byte[] buf = new byte[PACKET_SIZE];

                        Buffer.BlockCopy(dataTx, i * PACKET_SIZE, buf, 0, PACKET_SIZE);

                        // Write then read back the data...
                        double t1 = DateTime.Now.TimeOfDay.TotalSeconds;
                        await dev.WriteAsync(buf, (uint)PACKET_SIZE);
                        double t2 = DateTime.Now.TimeOfDay.TotalSeconds;

                        double t3 = DateTime.Now.TimeOfDay.TotalSeconds;
                        uint count = await dev.ReadAsync(dataRx, (uint)PACKET_SIZE);
                        double t4 = DateTime.Now.TimeOfDay.TotalSeconds;

                        if (count < PACKET_SIZE)
                        {
                            errorCode = (int)ERROR_CODES.FAILED_TO_READ_ALL_DATA;
                            return false;
                        }

                        double span = t4 - t3;
                        //AppendConsole(span.ToString());

                        double t5 = DateTime.Now.TimeOfDay.TotalSeconds;
                        for (int j = 0; j < PACKET_SIZE; j++)
                        {
                            if (buf[j] != dataRx[j])
                            {
                                errorCode = (int)ERROR_CODES.DATA_INTEGRITY;
                                return false;
                            }
                        }
                        double t6 = DateTime.Now.TimeOfDay.TotalSeconds;
                    }
                    dev.Close();

                    return true;
                }).AsAsyncOperation();

                double finish = DateTime.Now.TimeOfDay.TotalSeconds;
                s = String.Format(
                            @"Finished LoopbackTest:
                                Result: {0}
                                ErrorCode: {1}
                                Duration: {2}secs",
                                res.ToString().ToLower(),
                                errorCode,
                                Math.Round(finish - start, 2));
                AppendLogFile(s);
                AppendConsole(s);

                return res;
            }
            catch
            {
                return false;
            }
        }

        /// <summary>
        /// Tests the QueueStatus property of an IFTDevice.
        /// </summary>
        /// <param name="ftManager">The ftManager instance.</param>
        /// <param name="deviceID">The device identifier.</param>
        /// <returns>Task{Boolean}.</returns>
        public async Task<Boolean> QueueStatusTest(FTManager ftManager, String deviceID)
        {
            try
            {
                String s = "";
                double start = 0;
                int errorCode = (int) ERROR_CODES.SUCCESS;
                uint TOTAL_BYTES = 32769;
                uint PACKET_SIZE = 1024;
                uint iterations = TOTAL_BYTES / PACKET_SIZE;

                Boolean res = await Task.Run<Boolean>(async () =>
                {
                    byte[] dataTx = new byte[TOTAL_BYTES];
                    byte[] dataRx = new byte[TOTAL_BYTES];

                    // Generate some random data...
                    Random rnd = new Random();
                    for (int j = 0; j < dataTx.Length; j++)
                    {
                        dataTx[j] = (byte)rnd.Next(0, 0xff);
                    }

                    // Create device list...
                    var devList = ftManager.GetDeviceList();
                    if (devList.Count == 0)
                    {
                        errorCode = (int)ERROR_CODES.NO_DEVICES_FOUND;
                    }

                    // Find device in the list again...
                    IFTDevice dev = ftManager.OpenByDeviceID(deviceID);
                    if (dev == null)
                    {
                        errorCode = (int)ERROR_CODES.FAILED_TO_OPEN;
                    }

                    await SetUARTSettings(dev);

                    start = DateTime.Now.TimeOfDay.TotalSeconds;
                    s = "\r\n\r\nStarted QueueStatusTest\r\n";
                    AppendLogFile(s);
                    AppendConsole(s);

                    await dev.WriteAsync(dataTx, 128);
                    dev.Purge(true, false);

                    for (int j = 0; j < TOTAL_BYTES; j++)
                    {
                        dataTx[j] = (byte)j;
                    }

                    await dev.ResetAsync();

                    await dev.WriteAsync(dataTx, 10);

                    while (dev.GetQueueStatus() != 10)
                    {
                        //return false;
                    }

                    if (await dev.ReadAsync(dataRx, 10) != 10)
                        return false;

                    for (int j = 0; j < 10; j++)
                    {
                        if (dataTx[j] != dataRx[j])
                        {
                            errorCode = (int)ERROR_CODES.DATA_INTEGRITY;
                            return false;
                        }
                    }

                    dev.Close();

                    return true;
                }).AsAsyncOperation();

                double finish = DateTime.Now.TimeOfDay.TotalSeconds;
                s = String.Format(
                            @"Finished QueueStatusTest:
                                Result: {0}
                                ErrorCode: {1}
                                Duration: {2}secs",
                                res.ToString().ToLower(),
                                errorCode,
                                Math.Round(finish - start, 2));
                AppendLogFile(s);
                AppendConsole(s);

                return res;
            }
            catch
            {
                return false;
            }
        }

        private async void ReadEEPROM()
        {
            // if (myDevice != null)
            {
                string s = FTManager.GetLibraryVersion();
                AppendConsole(s);
                /*IFT_EEPROM ee = await myDevice.EepromRead();

                if (myDevice.DeviceInfoNode.DeviceType == DEVICE_TYPE.FT232R)
                {
                    // Cast to the type that corresponds to the device type.
                    FT232R_EEPROM eeData = ee as FT232R_EEPROM;

                    if (eeData == null)
                        return;

                    Debug.WriteLine(@"Manufacturer: {0}\r\nSerial Number: {1}\r\nProduct Description: {2}\r\n\r\n ",
                        eeData.Manufacturer, eeData.SerialNumber, eeData.Product);
                }*/
            }
        }
        
        private async Task MultiThreadedReadWrite()
        {
            int errorCode = (int)ERROR_CODES.SUCCESS;
            
            // Create device list...
            var devList = ftManager.GetDeviceList();
            if (devList.Count == 0)
            {
                errorCode = (int)ERROR_CODES.NO_DEVICES_FOUND;
            }

            // Find device in the list again...
            IFTDevice dev = ftManager.OpenByDeviceID(devList[0].DeviceId);
            if (dev == null)
            {
                errorCode = (int)ERROR_CODES.FAILED_TO_OPEN;
                return;
            }

            await SetUARTSettings(dev);

            byte[] dataTx = new byte[10];
            byte[] dataRx = new byte[10];

            var task1 = Windows.System.Threading.ThreadPool.RunAsync(
            async (workItem) =>
            {

                while (true)
                {
                    // Generate some random data...
                    Random rnd = new Random();
                    for (int j = 0; j < dataTx.Length; j++)
                    {
                        dataTx[j] = (byte)rnd.Next(0, 0xff);
                    }

                    await dev.WriteAsync(dataTx, (uint)10);
                }
            }).AsTask();

            var task2 = Windows.System.Threading.ThreadPool.RunAsync(
            async (workItem) =>
            {

                while (true)
                {
                    uint count = await dev.ReadAsync(dataRx, (uint)10);

                    if (count < 10)
                        return;

                }
            }).AsTask();

#if DAVE
            var task1 = Windows.System.Threading.ThreadPool.RunAsync(
            async (workItem) =>
            {
                byte[] dataTx = new byte[10];
                byte[] dataRx = new byte[10];

                // Create device list...
                var devList = ftManager.GetDeviceList();
                if (devList.Count == 0)
                {
                    errorCode = (int)ERROR_CODES.NO_DEVICES_FOUND;
                }

                // Find device in the list again...
                IFTDevice dev = ftManager.OpenByDeviceID(devList[0].DeviceId);
                if (dev == null)
                {
                    errorCode = (int)ERROR_CODES.FAILED_TO_OPEN;
                    return;
                }

                await SetUARTSettings(dev);
                
                // Generate some random data...
                Random rnd = new Random();
                for (int j = 0; j < dataTx.Length; j++)
                {
                    dataTx[j] = (byte)rnd.Next(0, 0xff);
                }

                // Write then read back the data...
                await dev.Write(dataTx, (uint)10);
                uint count = dev.Read(dataRx, (uint)10);

                if (count < 10)
                {
                    errorCode = (int)ERROR_CODES.FAILED_TO_READ_ALL_DATA;
                    return;
                }

                for (int j = 0; j < 10; j++)
                {
                    if (dataTx[j] != dataRx[j])
                    {
                        errorCode = (int)ERROR_CODES.DATA_INTEGRITY;
                        return;
                    }
                }
                dev.Close();

            }).AsTask();

            //await task1;
            task1.Wait();
#endif
#if DAVE
            while (task1.Status == TaskStatus.Running)
                ;

            var task2 = Windows.System.Threading.ThreadPool.RunAsync(
            async (workItem) =>
            {
                byte[] dataTx = new byte[10];
                byte[] dataRx = new byte[10];

                // Create device list...
                var devList = ftManager.GetDeviceList();
                if (devList.Count == 0)
                {
                    errorCode = (int)ERROR_CODES.NO_DEVICES_FOUND;
                    return;
                }

                // Find device in the list again...
                IFTDevice dev = ftManager.OpenByDeviceID(devList[0].DeviceId);
                if (dev == null)
                {
                    errorCode = (int)ERROR_CODES.FAILED_TO_OPEN;
                    return;
                }

                await SetUARTSettings(dev);

                // Generate some random data...
                Random rnd = new Random();
                for (int j = 0; j < dataTx.Length; j++)
                {
                    dataTx[j] = (byte)rnd.Next(0, 0xff);
                }

                // Write then read back the data...
                await dev.Write(dataTx, (uint)10);
                uint count = dev.Read(dataRx, (uint)10);

                if (count < 10)
                {
                    errorCode = (int)ERROR_CODES.FAILED_TO_READ_ALL_DATA;
                    return;
                }

                for (int j = 0; j < 10; j++)
                {
                    if (dataTx[j] != dataRx[j])
                    {
                        errorCode = (int)ERROR_CODES.DATA_INTEGRITY;
                        return;
                    }
                }

                dev.Close();
            }).AsTask();

            await task2;
#endif
        }

        private async void ProgramEEPROM()
        {
            if (myDevice == null)
                return;

            if (myDevice.DeviceInfoNode.DeviceType != DEVICE_TYPE.FT232R)
                return;

            FT232R_EEPROM ee = new FT232R_EEPROM();

            ee.VendorID = 0x0403;
            ee.ProductID = 0x6001;
            ee.LoadVCP = true;
            ee.Manufacturer = "FTDI";
            ee.Product = "FT232R";
            ee.SerialNumber = "FT7654321";
            ee.SerialNumberEnable = true;
            ee.UsbVersion = USB_VERSION.USB_20;
            ee.SelfPowered = false;
            ee.RemoteWakeupEnable = false;
            ee.PullDownEnable = false;
            ee.MaxPower = 500;
            ee.InvertTXD = false;
            ee.InvertRXD = false;
            ee.InvertRTS = false;
            ee.InvertRI = false;
            ee.InvertDTR = false;
            ee.InvertDSR = false;
            ee.InvertDCD = false;
            ee.InvertCTS = false;
            ee.HighIO = false;
            ee.ExternalOscillatorEnable = false;
            ee.CBus4 = FTDI.D2xx.WinRT.Device.EEPROM.FT232R.CBUS_SIGNALS.TXDEN;
            ee.CBus3 = FTDI.D2xx.WinRT.Device.EEPROM.FT232R.CBUS_SIGNALS.TXDEN;
            ee.CBus2 = FTDI.D2xx.WinRT.Device.EEPROM.FT232R.CBUS_SIGNALS.TXDEN;
            ee.CBus1 = FTDI.D2xx.WinRT.Device.EEPROM.FT232R.CBUS_SIGNALS.TXDEN;
            ee.CBus0 = FTDI.D2xx.WinRT.Device.EEPROM.FT232R.CBUS_SIGNALS.TXDEN;

            await myDevice.EepromProgramAsync(ee);
        }

        private async void btnListDevices_Click(object sender, RoutedEventArgs e)
        {
            UInt32 id = 0;
            String s = "Testing Started " + DateTime.Now.ToString();
            AppendLogFile(s);
            AppendConsole(s);
            s = Environment.NewLine + "----------------------------------------";
            AppendLogFile(s);
            AppendConsole(s);
            
            var devList = ftManager.GetDeviceList(); 
            foreach (IFTDeviceInfoNode node in devList)
            {
                /*var dev = ftManager.OpenByDescription(node.Description);

                IChipId chipId = dev.ChipId;

                if (chipId != null)
                {
                    id = await chipId.GetId();
                }*/

                // await OpenCloseTest(ftManager, node.DeviceId);
                await OpenCloseLoopbackTest(ftManager, node.DeviceId);
                // await LoopbackTest(ftManager, node.DeviceId);
                // await MultiThreadedReadWrite();
                // await QueueStatusTest(ftManager, node.DeviceId);
            }

            AppendLogFile(s);
            AppendConsole(s);
            s = "\r\nTesting Finished " + DateTime.Now.ToString() + "\r\n"; 
            AppendLogFile(s);
            AppendConsole(s);
        }

        private void AppendLogFile(String s)
        {
            try
            {
                if (file == null)
                    return;
               
                var t = FileIO.AppendTextAsync(file, s).AsTask();
                t.Wait(); // Wait for this to complete...        
            }
            catch
            { }
        }

        private async void AppendConsole(String s)
        {
            await MainPage.Dispatcher.RunAsync(Windows.UI.Core.CoreDispatcherPriority.Low, 
            () => 
            {
                txtConsole.Text += s;
            });
        }

        private void btnReadEEPROM_Click(object sender, RoutedEventArgs e)
        {
            ReadEEPROM();
        }

        private void btnProgramEEPROM_Click(object sender, RoutedEventArgs e)
        {
            ProgramEEPROM();
        }



        private async void cbBaudRate_SelectionChanged(object sender, SelectionChangedEventArgs e)
        {
#if DAVE
            if (FtDevice == null)
                return;

            ComboBoxItem br = (ComboBoxItem)cbBaudRate.SelectedItem;
            UInt32 baudRate = Convert.ToUInt32(br.Content);
            await FtDevice.SetBaudRate(baudRate);
#endif
        }

        private async void cbFlowControl_SelectionChanged(object sender, SelectionChangedEventArgs e)
        {
#if DAVE
            if (FtDevice == null)
                return;

            ComboBoxItem fc = (ComboBoxItem)cbFlowControl.SelectedItem;
            FLOW_CONTROL flowControl = (FLOW_CONTROL)Enum.Parse(typeof(FLOW_CONTROL), (String)fc.Tag);
            await FtDevice.SetFlowControl(flowControl, 0x00, 0x00);
#endif
        }

        private void cbParity_SelectionChanged(object sender, SelectionChangedEventArgs e)
        {
#if DAVE
            SetDataCharacteristics();
#endif
        }

        private void cbStopBits_SelectionChanged(object sender, SelectionChangedEventArgs e)
        {
#if DAVE
            SetDataCharacteristics();
#endif
        }

        private void cbDataBits_SelectionChanged(object sender, SelectionChangedEventArgs e)
        {
#if DAVE
            SetDataCharacteristics();
#endif
        }

        async private void  btnPurgeTest_Click(object sender, RoutedEventArgs e)
        {
            UInt32 id = 0;
            String s = "Testing Started " + DateTime.Now.ToString();
            AppendLogFile(s);
            AppendConsole(s);
            s = Environment.NewLine + "----------------------------------------";
            AppendLogFile(s);
            AppendConsole(s);

            var devList = ftManager.GetDeviceList();
            foreach (IFTDeviceInfoNode node in devList)
            {
                /*var dev = ftManager.OpenByDescription(node.Description);

                IChipId chipId = dev.ChipId;

                if (chipId != null)
                {
                    id = await chipId.GetId();
                }*/

                // await OpenCloseTest(ftManager, node.DeviceId);
                // await OpenCloseLoopbackTest(ftManager, node.DeviceId);
                // await LoopbackTest(ftManager, node.DeviceId);
                // await MultiThreadedReadWrite();
                //await QueueStatusTest(ftManager, node.DeviceId);
                await PurgeTest(ftManager, node.DeviceId);
            }

            AppendLogFile(s);
            AppendConsole(s);
            s = "\r\nTesting Finished " + DateTime.Now.ToString() + "\r\n";
            AppendLogFile(s);
            AppendConsole(s);
        }

        /// <summary>
        /// Tests the Purging of a device
        /// </summary>
        /// <param name="ftManager">The ftManager instance.</param>
        /// <param name="deviceID">The device identifier.</param>
        /// <returns>Task{Boolean}.</returns>
        public async Task<Boolean> PurgeTest(FTManager ftManager, String deviceID)
        {
            try
            {
                int errorCode = (int)ERROR_CODES.SUCCESS;

                double start = DateTime.Now.TimeOfDay.TotalSeconds;
                String s = "\r\n\r\nStarted PurgeLoopbackTest\r\n";
                AppendLogFile(s);
                AppendConsole(s);

                Boolean res = await Task.Run<Boolean>(async () =>
                {
                    for (int i = 0; i < 100; i++)
                    {
                        byte[] dataTx = new byte[10];
                        byte[] dataRx = new byte[10];

                        // Create device list...
                        var devList = ftManager.GetDeviceList();
                        if (devList.Count == 0)
                        {
                            errorCode = (int)ERROR_CODES.NO_DEVICES_FOUND;
                        }

                        // Find device in the list again...
                        IFTDevice dev = ftManager.OpenByDeviceID(deviceID);
                        if (dev == null)
                        {
                            errorCode = (int)ERROR_CODES.FAILED_TO_OPEN;
                        }

                        await SetUARTSettings(dev);

                        // Generate some random data...
                        Random rnd = new Random();
                        for (int j = 0; j < dataTx.Length; j++)
                        {
                            dataTx[j] = (byte)rnd.Next(0, 0xff);
                        }
                        // Write then read back the data...
                        await dev.WriteAsync(dataTx, (uint)dataTx.Length);
                        dev.Purge(true, false);

                        for (int j = 0; j < dataTx.Length; j++)
                        {
                            dataTx[j] = (byte)rnd.Next(0, 0xff);
                        }
                        // Write then read back the data...
                        await dev.WriteAsync(dataTx, (uint)dataTx.Length);

                        uint count = await dev.ReadAsync(dataRx, (uint)dataTx.Length);
                        if (count < dataTx.Length)
                        {
                            errorCode = (int)ERROR_CODES.FAILED_TO_READ_ALL_DATA;
                            dev.Close();
                            return false;
                        }

                        for (int j = 0; j < dataTx.Length; j++)
                        {
                            if (dataTx[j] != dataRx[j])
                            {
                                errorCode = (int)ERROR_CODES.DATA_INTEGRITY;
                                return false;
                            }
                        }

                        dev.Close();
                    }

                    return true;
                }).AsAsyncOperation();

                double finish = DateTime.Now.TimeOfDay.TotalSeconds;
                s = String.Format(
                            @"Finished PurgeLoopbackTest:
                                Result: {0}
                                ErrorCode: {1}
                                Duration: {2}secs",
                                res.ToString().ToLower(),
                                errorCode,
                                Math.Round(finish - start, 2));
                AppendLogFile(s);
                AppendConsole(s);

                return res;
            }
            catch
            {
                return false;
            }

        }


        private void btnTest_Click(object sender, RoutedEventArgs e)
        {
            String s ="";
            try
            {
                UInt32 id = 0;
                s = "Testing Started " + DateTime.Now.ToString();
                AppendLogFile(s);
                AppendConsole(s);
                s = Environment.NewLine + "----------------------------------------";
                AppendLogFile(s);
                AppendConsole(s);
                s = "\n";
                var devList = ftManager.GetDeviceList();
                foreach (IFTDeviceInfoNode node in devList)
                {
                    if(node.Description == null)
                    {
                        Debug.WriteLine("description is null");
                        continue;
                    }
                    var dev = ftManager.OpenByDescription(node.Description);
                    if (dev != null)
                    {
                        s += "Device Opened: " + node.Description + "\n";
                    }
                    else
                    {
                        s += "Device Failed to Open, OpenByDescription returned null device.\n";
                    }
                    ////////////////////////////////////////////////////////////////////////////                    
                    //
                    // Your Code to do some comms stuff on the dev goes here.
                    //
                    ////////////////////////////////////////////////////////////////////////////
                    if (dev != null) 
                    {
                        dev.Close();
                        s += "Device Closed.";
                    }                    
                }

                AppendLogFile(s);
                AppendConsole(s);
                s = "\r\nTest Finished " + DateTime.Now.ToString() + "\r\n";
                AppendLogFile(s);
                AppendConsole(s);
            }
            catch(Exception ex)
            {
                s += "\n\n\nTest Caught Exception\n";
                
                Debug.WriteLine("Test Caught ex: {0}", ex.Message);
                AppendLogFile(s);
                AppendConsole(s);
            }
        }
        /// <summary>
        /// Invoked when application execution is being suspended.  Application state is saved
        /// without knowing whether the application will be terminated or resumed with the contents
        /// of memory still intact.
        /// </summary>
        /// <param name="sender">The source of the suspend request.</param>
        /// <param name="e">Details about the suspend request.</param>
        private void OnSuspending(object sender, SuspendingEventArgs e)
        {
            var deferral = e.SuspendingOperation.GetDeferral();
            //TODO: Save application state and stop any background activity            
            ftManager.Suspend();

            deferral.Complete();
        }


        /// <summary>
        /// Invoked when application execution is Resumeded.
        /// </summary>
        /// <param name="sender">The source of the suspend request.</param>
        /// <param name="e">Details about the suspend request.</param>
        private void OnResuming(object sender, object e)
        {         
            ftManager.Resume();
        }


        private IFTDevice dev;

        private void btnOpen_Click(object sender, RoutedEventArgs e)
        {
            if (dev != null)
                dev.Close();

            // Create device list...
            var devList = ftManager.GetDeviceList();
            if (devList.Count == 0)
            {
                return;
            }

            // Find device in the list again...
            dev = ftManager.OpenByDeviceID(devList[0].DeviceId);
            if (dev == null)
            {
                return;
            }
        }
        
        private void btnClose_Click(object sender, RoutedEventArgs e)
        {
            if (dev == null)
                return;

            dev.Close();
        }

        private void btnRead_Click(object sender, RoutedEventArgs e)
        {
            if (dev == null)
                return;

            Task<String> t = Task.Run(async () =>
            {
                uint len = dev.GetQueueStatus();
                if (len == 0)
                    return null;

                byte[] data = new byte[len];

                uint read = await dev.ReadAsync(data, len);
                if (read != len)
                    return null;

                string result = System.Text.Encoding.UTF8.GetString(data, 0, (int) len);
                return result;
            });

            AppendConsole(t.Result);
        }

        private  void btnWrite_Click(object sender, RoutedEventArgs e)
        {
            const string str = "FTDI";

            if (dev == null)
                return;

            var t = Task.Factory.StartNew(async () =>
            {

                byte[] bytes = new byte[str.Length*sizeof (char)];
                Buffer.BlockCopy(str.ToCharArray(), 0, bytes, 0, bytes.Length);

                await dev.WriteAsync(bytes, (uint)bytes.Length);
            });
        }

    }
}
