#pragma once
#include <stdexcept>

// Settings interfaces belong to the Settings COM identity, not the view.
// Keep both original references until configuration succeeds or is refused.
template<class Settings, class Settings4, class View, class IID, class Check>
void configureDesktopSettings(View* view, const IID& settings4IID, Check check) {
    Settings* settings=nullptr;
    Settings4* extended=nullptr;
    try {
        check(view->get_Settings(&settings));
        if(!settings)throw std::runtime_error("DESKTOP_SETTINGS_UNAVAILABLE");
        check(settings->put_AreHostObjectsAllowed(FALSE));
        check(settings->put_IsWebMessageEnabled(FALSE));
        check(settings->put_AreDevToolsEnabled(FALSE));
        check(settings->put_AreDefaultContextMenusEnabled(FALSE));
        check(settings->put_AreDefaultScriptDialogsEnabled(FALSE));
        check(settings->QueryInterface(settings4IID,reinterpret_cast<void**>(&extended)));
        if(!extended)throw std::runtime_error("DESKTOP_SETTINGS4_UNAVAILABLE");
        check(extended->put_IsPasswordAutosaveEnabled(FALSE));
        check(extended->put_IsGeneralAutofillEnabled(FALSE));
    } catch(...) {
        if(extended)extended->Release();
        if(settings)settings->Release();
        throw;
    }
    extended->Release();
    settings->Release();
}
