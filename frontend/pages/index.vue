<template>
  <div>
    <SearchBox @select="onArtistSelect" />
    <div v-if="selectedArtist" class="mt-8">
      <LiveSchedule :artist="selectedArtist" />
    </div>
  </div>
</template>

<script setup lang="ts">
const selectedArtist = ref<string>('')

const onArtistSelect = (artist: string) => {
  selectedArtist.value = artist
  // 空文字の場合はスケジュールをクリア
  // artist が空文字の時は v-if="selectedArtist" により LiveSchedule が非表示になる
}
</script>