<template>
  <div class="bg-gray-50">
    <div class="container mx-auto px-8 py-16 min-h-screen max-w-[640px]">
      <h1 class="text-2xl font-bold mb-10 text-center" @click="clearSelections">
        <span class="cursor-pointer">
          <img src="/images/logo.svg" alt="LiveSearch" class="h-6 text-center inline-block" />
        </span>
        <span class="text-sm font-normal text-gray-600 block mt-2">ライブ情報を一括検索</span>
      </h1>
 
      <DateSelector
        class="mb-6"
        @select="onDateSelect"
        @clear="onDateClear"
      />
      
      <div v-if="!selectedDate">
        <SearchBox @select="onArtistSelect" />
        <div v-if="selectedArtist" class="mt-8">
          <LiveSchedule :artist="selectedArtist" />
        </div>
      </div>
 
      <div v-else class="mt-8">
        <DateSchedule :date="selectedDate" />
      </div>
    </div>
  </div>
 </template>

<script setup lang="ts">
const selectedArtist = ref<string>('')
const selectedDate = ref<string>('')

const clearSelections = () => {
 selectedArtist.value = ''
 selectedDate.value = ''
}

const onArtistSelect = (artist: string) => {
 selectedArtist.value = artist
 selectedDate.value = ''
}

const onDateSelect = (date: string) => {
 selectedDate.value = date
 selectedArtist.value = ''
}

const onDateClear = () => {
 selectedDate.value = ''
 selectedArtist.value = ''
}
</script>