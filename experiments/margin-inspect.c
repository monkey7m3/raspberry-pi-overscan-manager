// Read-only connector margin inspector. Build: cc -Wall -Wextra -O2
// -o margin-inspect margin-inspect.c $(pkg-config --cflags --libs libdrm)
// Usage: ./margin-inspect /dev/dri/card1 35
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <xf86drm.h>
#include <xf86drmMode.h>

int main(int argc, char **argv) {
 if (argc != 3) {
  fprintf(stderr, "Usage: %s /dev/dri/cardN connector-id\n", argv[0]);
  return 2;
 }
 char *end = NULL;
 errno = 0;
 unsigned long id = strtoul(argv[2], &end, 10);
 if (errno || end == argv[2] || *end || id == 0 || id > UINT32_MAX) {
  fprintf(stderr, "Invalid connector ID\n"); return 2;
 }
 int fd = open(argv[1], O_RDONLY | O_CLOEXEC);
 if (fd < 0) { perror("open DRM device"); return 1; }
 drmModeObjectPropertiesPtr props = drmModeObjectGetProperties(fd,
  (uint32_t)id, DRM_MODE_OBJECT_CONNECTOR);
 if (!props) { perror("drmModeObjectGetProperties"); close(fd); return 1; }
 const char *names[] = {"left margin", "right margin", "top margin", "bottom margin"};
 uint32_t found = 0;
 for (uint32_t i = 0; i < props->count_props; ++i) {
  drmModePropertyPtr prop = drmModeGetProperty(fd, props->props[i]);
  if (!prop) continue;
  for (unsigned j = 0; j < 4; ++j) {
   if (strcmp(prop->name, names[j]) == 0) {
    printf("%s: property_id=%" PRIu32 " value=%" PRIu64 "\n",
     names[j], props->props[i], props->prop_values[i]);
    found |= 1u << j;
   }
  }
  drmModeFreeProperty(prop);
 }
 drmModeFreeObjectProperties(props);
 close(fd);
 if (found != 15) {
  fprintf(stderr, "Missing margin properties (mask=0x%x)\n", found);
  return 1;
 }
 return 0;
}
