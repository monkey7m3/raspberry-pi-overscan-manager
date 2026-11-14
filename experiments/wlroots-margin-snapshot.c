#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <xf86drmMode.h>

/*
 * Read-only DRM connector margin discovery helper.
 * Uses the compositor's existing DRM fd and connector id. Does not request
 * DRM master, submit commits, or change properties.
 */
struct margin_snapshot {
	uint32_t ids[4];
	uint64_t values[4];
};

static bool read_margin_snapshot(int drm_fd, uint32_t connector_id,
		struct margin_snapshot *out) {
	static const char *names[4] = {
		"left margin", "right margin", "top margin", "bottom margin"
	};
	memset(out, 0, sizeof(*out));
	drmModeObjectPropertiesPtr props = drmModeObjectGetProperties(
		drm_fd, connector_id, DRM_MODE_OBJECT_CONNECTOR);
	if (props == NULL) {
		return false;
	}
	for (uint32_t i = 0; i < props->count_props; ++i) {
		drmModePropertyPtr prop = drmModeGetProperty(drm_fd, props->props[i]);
		if (prop == NULL) {
			continue;
		}
		for (unsigned int j = 0; j < 4; ++j) {
			if (strcmp(prop->name, names[j]) == 0) {
				out->ids[j] = props->props[i];
				out->values[j] = props->prop_values[i];
				break;
			}
		}
		drmModeFreeProperty(prop);
	}
	drmModeFreeObjectProperties(props);
	for (unsigned int j = 0; j < 4; ++j) {
		if (out->ids[j] == 0) {
			return false;
		}
	}
	return true;
}
