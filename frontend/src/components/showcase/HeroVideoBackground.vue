<template>
  <video
    class="hero-video-bg"
    autoplay
    muted
    loop
    playsinline
    poster="/login-bg-poster.svg"
    aria-hidden="true"
  >
    <source src="/login-bg.mp4" type="video/mp4" />
  </video>
</template>

<style scoped>
.hero-video-bg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0.22;
  filter: saturate(0.85) brightness(0.65);
  pointer-events: none;
}
</style>
