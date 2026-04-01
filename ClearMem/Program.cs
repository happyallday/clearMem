using System;
using System.IO;
using System.Diagnostics;
using System.Threading;
using System.Threading.Tasks;
using System.Text.Json;
using System.Windows.Forms;

namespace ClearMem
{
    public class Config
    {
        public string TargetPath { get; set; } = @"D:\cache\.ws";
        public bool EnableTimer { get; set; } = false;
        public string TimerType { get; set; } = "interval";
        public int TimerIntervalMinutes { get; set; } = 60;
        public string TimerTime { get; set; } = "03:00";
        public bool EnableRdp { get; set; } = true;
    }

    static class Program
    {
        private static Config config;
        private static NotifyIcon notifyIcon;
        private static Mutex mutex;
        private static CancellationTokenSource cts = new CancellationTokenSource();
        private static string configPath = "config.json";
        private static System.Windows.Forms.Timer timer;

        [STAThread]
        static void Main()
        {
            mutex = new Mutex(true, "ClearMem_SingleInstance", out bool createdNew);
            if (!createdNew)
            {
                MessageBox.Show("程序已在运行", "提示", MessageBoxButtons.OK, MessageBoxIcon.Information);
                return;
            }

            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            LoadConfig();
            InitNotifyIcon();
            
            Task.Run(() => StartServices());
            
            Application.Run();
        }

        static void LoadConfig()
        {
            try
            {
                if (File.Exists(configPath))
                {
                    string json = File.ReadAllText(configPath);
                    config = JsonSerializer.Deserialize<Config>(json) ?? new Config();
                }
                else
                {
                    config = new Config();
                }
            }
            catch
            {
                config = new Config();
            }
        }

        static void SaveConfig()
        {
            try
            {
                string json = JsonSerializer.Serialize(config, new JsonSerializerOptions { WriteIndented = true });
                File.WriteAllText(configPath, json);
            }
            catch { }
        }

        static void InitNotifyIcon()
        {
            notifyIcon = new NotifyIcon();
            notifyIcon.Icon = System.Drawing.SystemIcons.Application;
            notifyIcon.Text = "ClearMem";

            ContextMenuStrip menu = new ContextMenuStrip();
            ToolStripMenuItem itemShow = new ToolStripMenuItem("显示");
            itemShow.Click += (s, e) => ShowMainForm();
            ToolStripMenuItem itemClear = new ToolStripMenuItem("清除缓存");
            itemClear.Click += (s, e) => ClearDirectory(config.TargetPath);
            ToolStripMenuItem itemExit = new ToolStripMenuItem("退出");
            itemExit.Click += (s, e) => ExitApplication();
            
            menu.Items.Add(itemShow);
            menu.Items.Add(itemClear);
            menu.Items.Add(new ToolStripSeparator());
            menu.Items.Add(itemExit);
            
            notifyIcon.ContextMenuStrip = menu;
            notifyIcon.DoubleClick += (s, e) => ShowMainForm();
            notifyIcon.Visible = true;
        }

        static void StartServices()
        {
            if (config.EnableRdp)
            {
                Task.Run(() => RdpMonitorLoop());
            }
        }

        static async Task RdpMonitorLoop()
        {
            long lastLogonTime = 0;
            string targetPath = config.TargetPath;
            while (!cts.Token.IsCancellationRequested)
            {
                try
                {
                    if (CheckRdpLogon())
                    {
                        long now = DateTimeOffset.Now.ToUnixTimeSeconds();
                        if (now - lastLogonTime > 60)
                        {
                            ClearDirectory(targetPath);
                            lastLogonTime = now;
                        }
                    }
                }
                catch { }
                Thread.Sleep(10000);
            }
        }

        static bool CheckRdpLogon()
        {
            try
            {
                string script = @"
$events = Get-WinEvent -FilterHashtable @{LogName='Security'; ID=4624; StartTime=(Get-Date).AddMinutes(-2)} -MaxEvents 5 -ErrorAction SilentlyContinue
foreach ($e in $events) {
    $xml = [xml]$e.ToXml()
    $data = $xml.Event.EventData
    $logonType = ($data | Where-Object {$_.Name -eq 'LogonType'}).'#text'
    if ($logonType -eq '10') {
        Write-Output 'true'
    }
}
";
                ProcessStartInfo psi = new ProcessStartInfo()
                {
                    FileName = "powershell",
                    Arguments = $"-NoProfile -ExecutionPolicy Bypass -Command \"{script}\"",
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    CreateNoWindow = true
                };
                using (Process p = Process.Start(psi))
                {
                    string output = p.StandardOutput.ReadToEnd();
                    p.WaitForExit(10000);
                    return output.Trim().Contains("true");
                }
            }
            catch
            {
                return false;
            }
        }

        public static bool ClearDirectory(string path)
        {
            if (!Directory.Exists(path)) return false;
            try
            {
                int count = 0;
                foreach (string item in Directory.GetFileSystemEntries(path))
                {
                    try
                    {
                        if (File.Exists(item))
                        {
                            File.Delete(item);
                            count++;
                        }
                        else
                        {
                            Directory.Delete(item, true);
                            count++;
                        }
                    }
                    catch { }
                }
                return true;
            }
            catch
            {
                return false;
            }
        }

        static void ExitApplication()
        {
            cts.Cancel();
            if (timer != null)
            {
                timer.Stop();
                timer.Dispose();
            }
            notifyIcon.Visible = false;
            notifyIcon.Dispose();
            Application.Exit();
        }

        static void StartTimerService()
        {
            if (timer != null)
            {
                timer.Stop();
                timer.Dispose();
                timer = null;
            }

            if (config.EnableTimer)
            {
                timer = new System.Windows.Forms.Timer();
                timer.Interval = config.TimerIntervalMinutes * 60 * 1000;
                timer.Tick += (s, e) => ClearDirectory(config.TargetPath);
                timer.Start();
            }
        }

        static void SaveConfigAndRestartTimer()
        {
            SaveConfig();
            StartTimerService();
        }

        static void ShowMainForm()
        {
            Form form = new MainForm(config, SaveConfigAndRestartTimer, ClearDirectory);
            form.ShowDialog();
        }
    }

    public class MainForm : Form
    {
        private TextBox pathTextBox;
        private CheckBox rdpCheckBox;
        private CheckBox timerCheckBox;
        private RadioButton intervalRadio;
        private RadioButton timeRadio;
        private NumericUpDown intervalNumeric;
        private TextBox timeTextBox;
        private Config config;
        private Action saveAction;
        private Func<string, bool> clearAction;

        public MainForm(Config cfg, Action save, Func<string, bool> clear)
        {
            config = cfg;
            saveAction = save;
            clearAction = clear;
            InitUI();
            LoadSettings();
        }

        void InitUI()
        {
            this.Text = "ClearMem - 定时清除目录";
            this.Size = new System.Drawing.Size(450, 350);
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MaximizeBox = false;

            TabControl tab = new TabControl() { Dock = DockStyle.Fill };
            this.Controls.Add(tab);

            TabPage basicTab = new TabPage("基础设置");
            TabPage timerTab = new TabPage("定时设置");
            TabPage aboutTab = new TabPage("关于");
            tab.TabPages.Add(basicTab);
            tab.TabPages.Add(timerTab);
            tab.TabPages.Add(aboutTab);

            Panel basicPanel = new Panel() { Dock = DockStyle.Fill };
            basicTab.Controls.Add(basicPanel);
            
            Label lblPath = new Label() { Text = "目标目录:", Left = 20, Top = 20, Width = 70 };
            pathTextBox = new TextBox() { Left = 100, Top = 20, Width = 250 };
            Button btnBrowse = new Button() { Text = "浏览", Left = 360, Top = 18, Width = 50 };
            btnBrowse.Click += (s, e) => {
                using (FolderBrowserDialog fbd = new FolderBrowserDialog())
                {
                    if (fbd.ShowDialog() == DialogResult.OK) pathTextBox.Text = fbd.SelectedPath;
                }
            };
            rdpCheckBox = new CheckBox() { Text = "启用RDP登录自动清除", Left = 20, Top = 60, Width = 200 };
            basicPanel.Controls.AddRange(new Control[] { lblPath, pathTextBox, btnBrowse, rdpCheckBox });

            Panel timerPanel = new Panel() { Dock = DockStyle.Fill };
            timerTab.Controls.Add(timerPanel);
            timerCheckBox = new CheckBox() { Text = "启用定时清除", Left = 20, Top = 20, Width = 200 };
            timerCheckBox.CheckedChanged += (s, e) => SetTimerControls(timerCheckBox.Checked);
            intervalRadio = new RadioButton() { Text = "间隔清除", Left = 40, Top = 50, Width = 100 };
            intervalNumeric = new NumericUpDown() { Left = 150, Top = 48, Width = 60, Minimum = 1, Maximum = 1440, Value = 60 };
            Label lblMin = new Label() { Text = "分钟", Left = 215, Top = 50 };
            timeRadio = new RadioButton() { Text = "指定时间清除", Left = 40, Top = 80, Width = 100 };
            timeTextBox = new TextBox() { Left = 150, Top = 78, Width = 60, Text = "03:00" };
            timerPanel.Controls.AddRange(new Control[] { timerCheckBox, intervalRadio, intervalNumeric, lblMin, timeRadio, timeTextBox });

            Panel aboutPanel = new Panel() { Dock = DockStyle.Fill };
            aboutTab.Controls.Add(aboutPanel);
            aboutPanel.Controls.Add(new Label() { Text = "ClearMem", Left = 20, Top = 20, Font = new System.Drawing.Font("", 14, System.Drawing.FontStyle.Bold) });
            aboutPanel.Controls.Add(new Label() { Text = "版本: 1.0.0", Left = 20, Top = 50 });
            aboutPanel.Controls.Add(new Label() { Text = "功能: 定时/RDP登录自动清除目录", Left = 20, Top = 75 });
            aboutPanel.Controls.Add(new Label() { Text = "目录: D:\\cache\\.ws", Left = 20, Top = 100 });

            Panel btnPanel = new Panel() { Dock = DockStyle.Bottom, Height = 45 };
            this.Controls.Add(btnPanel);
            Button btnSave = new Button() { Text = "保存设置", Anchor = AnchorStyles.Right, Left = 250, Top = 10, Width = 80 };
            Button btnClear = new Button() { Text = "立即清除", Anchor = AnchorStyles.Right, Left = 160, Top = 10, Width = 80 };
            btnSave.Click += (s, e) => SaveSettings();
            btnClear.Click += (s, e) => {
                if (clearAction(config.TargetPath)) MessageBox.Show("目录已清除", "提示");
                else MessageBox.Show("清除失败", "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
            };
            btnPanel.Controls.Add(btnSave);
            btnPanel.Controls.Add(btnClear);
        }

        void LoadSettings()
        {
            pathTextBox.Text = config.TargetPath;
            rdpCheckBox.Checked = config.EnableRdp;
            timerCheckBox.Checked = config.EnableTimer;
            intervalRadio.Checked = config.TimerType == "interval";
            timeRadio.Checked = config.TimerType == "time";
            intervalNumeric.Value = config.TimerIntervalMinutes;
            timeTextBox.Text = config.TimerTime;
            SetTimerControls(config.EnableTimer);
        }

        void SetTimerControls(bool enabled)
        {
            intervalRadio.Enabled = enabled;
            intervalNumeric.Enabled = enabled && intervalRadio.Checked;
            timeRadio.Enabled = enabled;
            timeTextBox.Enabled = enabled && timeRadio.Checked;
            intervalRadio.CheckedChanged += (s, e) => intervalNumeric.Enabled = intervalRadio.Checked;
            timeRadio.CheckedChanged += (s, e) => timeTextBox.Enabled = timeRadio.Checked;
        }

        void SaveSettings()
        {
            config.TargetPath = pathTextBox.Text;
            config.EnableRdp = rdpCheckBox.Checked;
            config.EnableTimer = timerCheckBox.Checked;
            config.TimerType = intervalRadio.Checked ? "interval" : "time";
            config.TimerIntervalMinutes = (int)intervalNumeric.Value;
            config.TimerTime = timeTextBox.Text;
            saveAction();
            MessageBox.Show("设置已保存", "提示");
        }
    }
}