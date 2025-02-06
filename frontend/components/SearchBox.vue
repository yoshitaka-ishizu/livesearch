<template>
  <div class="relative">
    <!-- 検索フォーム部分 -->
    <div class="search-wrapper relative">
      <UInput
        v-model="searchQuery"
        placeholder="アーティスト名から探す"
        icon="i-heroicons-magnifying-glass"
        class="custom-input mb-3"
        @input="handleInput"
        @focus="handleFocus"
      />
      <!-- クリアボタン -->
      <UButton
        v-if="searchQuery"
        color="gray"
        variant="ghost"
        icon="i-heroicons-x-mark"
        class="clear-button"
        @click="clearSearch"
      />
    </div>
    
    <!-- 予測リスト -->
    <div v-if="shouldShowPredictions" 
         class="absolute w-full z-10 bg-white rounded-lg shadow-lg border border-gray-200 max-h-80 overflow-y-auto">
      <ul class="py-1">
        <li v-for="artist in displayedArtists" 
            :key="artist.name"
            class="px-4 py-3 hover:bg-gray-100 cursor-pointer flex justify-between items-center"
            :class="{ 'opacity-50 cursor-not-allowed hover:bg-white': !artist.hasSchedule }"
            @click="artist.hasSchedule && selectArtist(artist.name)">
          <span>{{ artist.name }}</span>
          <span v-if="!artist.hasSchedule" class="text-sm text-gray-400">
            ライブ予定なし
          </span>
        </li>
        
        <li v-if="totalResults > 20" 
            class="px-4 py-2 text-center text-blue-600 hover:bg-gray-100 cursor-pointer border-t"
            @click="showAllPopup = true">
          すべて表示 ({{ totalResults }}件)
        </li>
      </ul>
    </div>

    <!-- すべて表示ポップアップ -->
    <UModal v-model="showAllPopup">
      <div class="p-4">
        <h3 class="text-lg font-bold mb-4">アーティスト一覧</h3>
        <div class="max-h-96 overflow-y-auto">
          <ul class="space-y-2">
            <li v-for="artist in filteredArtists" 
                :key="artist.name"
                class="px-4 py-3 hover:bg-gray-100 cursor-pointer rounded flex justify-between items-center"
                :class="{ 'opacity-50 cursor-not-allowed hover:bg-white': !artist.hasSchedule }"
                @click="artist.hasSchedule && selectArtistAndClosePopup(artist.name)">
              <span>{{ artist.name }}</span>
              <span v-if="!artist.hasSchedule" class="text-sm text-gray-400">
                ライブ予定なし
              </span>
            </li>
          </ul>
        </div>
      </div>
    </UModal>
  </div>
</template>

<script setup lang="ts">
interface ArtistOption {
  name: string;
  hasSchedule: boolean;
}

const emit = defineEmits<{
  (e: 'select', artist: string): void
}>()

const { getArtistList } = useEvents()

const searchQuery = ref('')
const showAllPopup = ref(false)
const showPredictions = ref(false)
const isFocused = ref(false)
const artists = ref<ArtistOption[]>([])

// 予測リストの表示制御
const shouldShowPredictions = computed(() => {
  return searchQuery.value && 
         showPredictions.value && 
         displayedArtists.value.length > 0
})

// フィルタリング
const filteredArtists = computed(() => {
  if (!searchQuery.value || !artists.value?.length) return []
  
  const query = searchQuery.value.toLowerCase()
  return artists.value
    .filter(artist => artist.name.toLowerCase().startsWith(query))
    .sort((a, b) => a.name.localeCompare(b.name))
})

// 表示用の最大20件
const displayedArtists = computed(() => {
  return filteredArtists.value.slice(0, 20)
})

// 総結果数
const totalResults = computed(() => {
  return filteredArtists.value.length
})

// アーティスト一覧の取得
onMounted(async () => {
  try {
    const fetchedArtists = await getArtistList()
    artists.value = fetchedArtists
  } catch (error) {
    console.error('Failed to fetch artists:', error)
    artists.value = []
  }
})

// イベントハンドラー
const handleInput = () => {
  showPredictions.value = true
}

const handleFocus = () => {
  isFocused.value = true
  if (searchQuery.value) {
    showPredictions.value = true
  }
}

const selectArtist = (artist: string) => {
  searchQuery.value = artist
  showPredictions.value = false
  emit('select', artist)
}

const selectArtistAndClosePopup = (artist: string) => {
  selectArtist(artist)
  showAllPopup.value = false
}

const clearSearch = () => {
  searchQuery.value = ''
  showPredictions.value = false
  isFocused.value = false
  emit('select', '')
}

// クリックイベントのハンドリング
onMounted(() => {
  document.addEventListener('click', (e: MouseEvent) => {
    const target = e.target as HTMLElement
    if (!target.closest('.relative')) {
      showPredictions.value = false
      isFocused.value = false
    }
  })
})

// コンポーネントのクリーンアップ
onUnmounted(() => {
  document.removeEventListener('click', () => {})
})
</script>

<style scoped>
.search-wrapper {
  position: relative;
  width: 100%;
}

.custom-input {
  height: auto !important;
}

.custom-input :deep(input) {
  padding: 14px 14px 14px 40px !important;
  height: auto !important;
  text-align: left;
  padding-right: 48px !important;
}

.custom-input :deep(.icon) {
  height: 48px !important;
  padding: 14px 0 14px 14px;
  display: flex;
  align-items: center;
}

.clear-button {
  position: absolute !important;
  right: 0 !important;
  top: 0 !important;
  height: 48px !important;
  width: 48px !important;
  padding: 0 !important;
  background: transparent !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
}

.clear-button:hover {
  background: rgba(0, 0, 0, 0.05) !important;
}
</style>