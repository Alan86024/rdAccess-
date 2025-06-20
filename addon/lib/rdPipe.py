# RDAccess: Remote Desktop Accessibility for NVDA
# Copyright 2023 Leonard de Ruijter <alderuijter@gmail.com>
# License: GNU General Public License version 2.0

import os.path
import platform
import subprocess
import sysconfig
import winreg
from enum import StrEnum

import addonHandler
import COMRegistrationFixes
from logHandler import log

COM_CLS_CHANNEL_NAMES_VALUE_BRAILLE = "NVDA-BRAILLE"
COM_CLS_CHANNEL_NAMES_VALUE_SPEECH = "NVDA-SPEECH"
COM_CLASS_FOLDER = r"SOFTWARE\Classes\CLSID\{D1F74DC7-9FDE-45BE-9251-FA72D4064DA3}"
CTX_MODULES_FOLDER = r"SOFTWARE\Citrix\ICA Client\Engine\Configuration\Advanced\Modules"
CTX_RD_PIPE_FOLDER = os.path.join(CTX_MODULES_FOLDER, "DVCPlugin_RdPipe")
CTX_DVC_PLUGINS_FOLDER = os.path.join(CTX_MODULES_FOLDER, "DvcPlugins")
CTX_ARP_FOLDER = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\CitrixOnlinePluginPackWeb"
TS_ADD_INS_FOLDER = r"Software\Microsoft\Terminal Server Client\Default\AddIns\RdPipe"


def isCitrixSupported() -> bool:
	try:
		with winreg.OpenKey(
			winreg.HKEY_LOCAL_MACHINE,
			CTX_ARP_FOLDER,
			0,
			winreg.KEY_READ | winreg.KEY_WOW64_32KEY,
		):
			pass
	except OSError:
		return False
	try:
		with winreg.OpenKey(
			winreg.HKEY_CURRENT_USER,
			CTX_MODULES_FOLDER,
			0,
			winreg.KEY_READ | winreg.KEY_WOW64_32KEY,
		):
			return True
	except OSError:
		return False


class Architecture(StrEnum):
	X86 = "x86"
	AMD64 = "AMD64"
	ARM64 = "ARM64"


defaultArchitecture = Architecture(platform.machine())
match sysconfig.get_platform():
	case "win32":
		nvdaArchitecture = Architecture.X86
	case "win-amd64":
		nvdaArchitecture = Architecture.AMD64
	case "win-arm64":
		nvdaArchitecture = Architecture.ARM64
	case _:
		raise RuntimeError(f"Unsupported platform: {_}")


def execRegsrv(params: list[str], architecture: Architecture = defaultArchitecture) -> bool:
	if architecture is Architecture.X86:
		# Points to the 32-bit version, on Windows 32-bit or 64-bit.
		regsvr32 = os.path.join(COMRegistrationFixes.SYSTEM32, "regsvr32.exe")
	else:
		# SysWOW64 provides a virtual directory to allow 32-bit programs to reach 64-bit executables.
		regsvr32 = os.path.join(COMRegistrationFixes.SYSNATIVE, "regsvr32.exe")
	# Make sure a console window doesn't show when running regsvr32.exe
	startupInfo = subprocess.STARTUPINFO()
	startupInfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
	startupInfo.wShowWindow = subprocess.SW_HIDE
	try:
		subprocess.check_call([regsvr32, *params], startupinfo=startupInfo)
		return True
	except subprocess.CalledProcessError:
		log.exception(f"Error calling {regsvr32!r} with arguments {params!r}")
		return False


class CommandFlags(StrEnum):
	COM_SERVER = "c"
	RDP = "r"
	CITRIX = "x"


def getDllPath(architecture: Architecture = defaultArchitecture) -> str:
	addon = addonHandler.getCodeAddon()
	expectedPath = os.path.join(addon.path, "dll", f"rd_pipe_{architecture.lower()}.dll")
	if not os.path.isfile(expectedPath):
		raise FileNotFoundError(expectedPath)
	return expectedPath


def dllInstall(
	install: bool,
	comServer: bool,
	rdp: bool,
	citrix: bool,
	architecture: Architecture = defaultArchitecture,
) -> bool:
	path = getDllPath(architecture)
	command = ""
	if rdp:
		command += CommandFlags.RDP
	if citrix:
		command += CommandFlags.CITRIX
	if comServer:
		command += CommandFlags.COM_SERVER
		if install:
			command += f" {COM_CLS_CHANNEL_NAMES_VALUE_BRAILLE} {COM_CLS_CHANNEL_NAMES_VALUE_SPEECH}"
	cmdLine = ["/s", f'/i:"{command}"', "/n"]
	if not install:
		cmdLine.append("/u")
	cmdLine.append(path)
	return execRegsrv(cmdLine, architecture)
