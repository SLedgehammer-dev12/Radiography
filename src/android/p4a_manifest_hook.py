"""python-for-android hook: add the FileProvider entry to AndroidManifest.xml.

Buildozer can only inject XML attributes into the <application> tag
(`android.extra_manifest_application_arguments`), not child elements, and
`android.extra_manifest_xml` is a sibling of <application>. The FileProvider
is a child of <application>, so it is injected here.

The `after_apk_build` hook runs after p4a has rendered AndroidManifest.xml but
before gradle assembles the APK.
"""

import os

PROVIDER_MARKER = "androidx.core.content.FileProvider"

PROVIDER_XML = """        <provider
            android:name="androidx.core.content.FileProvider"
            android:authorities="${applicationId}.fileprovider"
            android:exported="false"
            android:grantUriPermissions="true">
            <meta-data
                android:name="android.support.FILE_PROVIDER_PATHS"
                android:resource="@xml/file_paths" />
        </provider>
"""


def after_apk_build(toolchain):
    dist_dir = getattr(getattr(toolchain, "_dist", None), "dist_dir", None)
    if not dist_dir:
        return
    manifest_path = os.path.join(dist_dir, "src", "main", "AndroidManifest.xml")
    if not os.path.exists(manifest_path):
        return

    with open(manifest_path, "r", encoding="utf-8") as handle:
        content = handle.read()

    if PROVIDER_MARKER in content:
        return  # already present (idempotent)

    if "</application>" not in content:
        return

    content = content.replace(
        "</application>", PROVIDER_XML + "    </application>", 1
    )
    with open(manifest_path, "w", encoding="utf-8") as handle:
        handle.write(content)
