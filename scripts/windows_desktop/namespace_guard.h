// Pure member-set policy shared by the Win32 scanner and portable fault checks.
#pragma once
#include <set>
#include <string>
using DesktopNames=std::set<std::wstring>;
inline bool exactDesktopNamespace(const DesktopNames& files,const DesktopNames& dirs,
                                  const DesktopNames& wantedFiles,const DesktopNames& wantedDirs){
 return files==wantedFiles&&dirs==wantedDirs;
}
