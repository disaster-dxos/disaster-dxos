// SPDX-License-Identifier: Apache-2.0
// AppDelegate của app hiện trường (khung từ template React Native 0.80). Thêm: nhận URL chuyển hướng OAuth
// `org.disasterdxos.cuutro:/oauthredirect` để react-native-app-auth hoàn tất đăng nhập Keycloak (PKCE).
import UIKit
import React
import React_RCTAppDelegate
import ReactAppDependencyProvider

@main
class AppDelegate: UIResponder, UIApplicationDelegate, RNAppAuthAuthorizationFlowManager {
  var window: UIWindow?

  var reactNativeDelegate: ReactNativeDelegate?
  var reactNativeFactory: RCTReactNativeFactory?

  // Bắt buộc theo giao thức RNAppAuthAuthorizationFlowManager (header trong Bridging-Header.h)
  public weak var authorizationFlowManagerDelegate: RNAppAuthAuthorizationFlowManagerDelegate?

  func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil
  ) -> Bool {
    let delegate = ReactNativeDelegate()
    let factory = RCTReactNativeFactory(delegate: delegate)
    delegate.dependencyProvider = RCTAppDependencyProvider()

    reactNativeDelegate = delegate
    reactNativeFactory = factory

    window = UIWindow(frame: UIScreen.main.bounds)

    factory.startReactNative(
      withModuleName: "CuuTroHienTruong",
      in: window,
      launchOptions: launchOptions
    )

    return true
  }

  // Keycloak chuyển hướng về app sau khi đăng nhập: trả URL cho AppAuth, URL khác cho React Native Linking
  func application(
    _ app: UIApplication,
    open url: URL,
    options: [UIApplication.OpenURLOptionsKey: Any] = [:]
  ) -> Bool {
    if let flow = authorizationFlowManagerDelegate, flow.resumeExternalUserAgentFlow(with: url) {
      return true
    }
    return RCTLinkingManager.application(app, open: url, options: options)
  }
}

class ReactNativeDelegate: RCTDefaultReactNativeFactoryDelegate {
  override func sourceURL(for bridge: RCTBridge) -> URL? {
    self.bundleURL()
  }

  override func bundleURL() -> URL? {
#if DEBUG
    RCTBundleURLProvider.sharedSettings().jsBundleURL(forBundleRoot: "index")
#else
    Bundle.main.url(forResource: "main", withExtension: "jsbundle")
#endif
  }
}
