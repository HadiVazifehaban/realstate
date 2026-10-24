package com.shekarchi.auth.util;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.PosixFilePermission;
import java.util.function.Function;

/** Reads a secret from its *_FILE mount first, with environment fallback for legacy deployments. */
public final class SecretValue {
    private SecretValue() {}

    public static String get(String name) {
        return get(name, System::getenv);
    }

    static String get(String name, Function<String, String> environment) {
        String file = environment.apply(name + "_FILE");
        if (file != null && !file.isBlank()) {
            try {
                Path path = Path.of(file);
                if (!Files.isRegularFile(path) || Files.size(path) > 16_384) {
                    throw new IllegalStateException("Secret file is unavailable");
                }
                var permissions = Files.getPosixFilePermissions(path);
                if (permissions.contains(PosixFilePermission.GROUP_READ)
                        || permissions.contains(PosixFilePermission.GROUP_WRITE)
                        || permissions.contains(PosixFilePermission.GROUP_EXECUTE)
                        || permissions.contains(PosixFilePermission.OTHERS_READ)
                        || permissions.contains(PosixFilePermission.OTHERS_WRITE)
                        || permissions.contains(PosixFilePermission.OTHERS_EXECUTE)) {
                    throw new IllegalStateException("Secret file permissions are too broad");
                }
                return Files.readString(path).stripTrailing();
            } catch (Exception ex) {
                throw new IllegalStateException("Configured secret file is unavailable", ex);
            }
        }
        return environment.apply(name);
    }
}
