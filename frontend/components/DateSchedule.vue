<template>
  <div>
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-xl font-bold">{{ formattedDate }}のライブスケジュール</h2>
      <span class="text-sm text-gray-500">{{ eventCount }}公演</span>
    </div>

    <div v-if="isLoading" class="text-center py-8">
      <USpinner />
    </div>
    
    <div v-else-if="events.length === 0" class="text-center py-8 text-gray-600">
      この日のライブ予定はありません
    </div>
    
    <div v-else class="space-y-4">
      <!-- 会場ごとにグループ化して表示 -->
      <div v-for="(venueEvents, venue) in groupedEvents" 
           :key="venue"
           class="bg-white rounded-lg shadow p-4">
        <div class="mb-2">
          <h3 class="text-lg font-bold">{{ venue }}</h3>
        </div>

        <div v-for="event in consolidatedEvents(venueEvents)"
             :key="event.title"
             class="border-t first:border-t-0 py-3">
          <!-- イベントタイトル -->
          <div class="font-medium text-lg mb-1">{{ event.title || '未設定' }}</div>
          
          <!-- 出演者一覧 -->
          <div class="text-gray-600 text-sm mb-2">
            {{ event.artists.join(', ') }}
          </div>

          <!-- 注記（昼公演など）があれば表示 -->
          <div v-if="event.note" class="text-blue-600 text-sm mb-2">
            {{ event.note }}
          </div>

          <!-- 詳細リンク -->
          <NuxtLink
            :to="event.url"
            target="_blank"
          >
            <UButton
              size="sm"
              variant="outline"
              color="gray"
            >
              詳細
            </UButton>
          </NuxtLink>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { format } from 'date-fns'
import { ja } from 'date-fns/locale'
import type { Schedule } from '~/types'

const props = defineProps<{
  date: string
}>()

const { getEventsByDate } = useEvents()
const events = ref<Schedule[]>([])
const isLoading = ref(true)

// イベントを会場ごとにグループ化
const groupedEvents = computed(() => {
  return events.value.reduce((acc, event) => {
    if (!acc[event.venue]) {
      acc[event.venue] = []
    }
    acc[event.venue].push(event)
    return acc
  }, {} as Record<string, Schedule[]>)
})

// 同じイベントをまとめる
const consolidatedEvents = (venueEvents: Schedule[]) => {
  // イベントタイトルでグループ化
  const groupedByTitle = venueEvents.reduce((acc, event) => {
    const key = event.title || '未設定'
    if (!acc[key]) {
      acc[key] = {
        title: event.title,
        artists: [],
        note: event.note,
        url: event.url
      }
    }
    acc[key].artists.push(event.artist)
    return acc
  }, {} as Record<string, { title: string, artists: string[], note: string, url: string }>)

  return Object.values(groupedByTitle)
}

// ライブ数を計算（イベントタイトルの重複を除いた数）
const eventCount = computed(() => {
  const uniqueEvents = new Set()
  events.value.forEach(event => {
    uniqueEvents.add(`${event.venue}-${event.title}`)
  })
  return uniqueEvents.size
})

// 日付のフォーマット
const formattedDate = computed(() => {
  const date = new Date(props.date)
  return `${format(date, 'M月d日', { locale: ja })}(${format(date, 'E', { locale: ja })})`
})

// データ取得
watch(() => props.date, async (newDate) => {
  if (newDate) {
    isLoading.value = true
    try {
      events.value = await getEventsByDate(newDate)
    } catch (error) {
      console.error('Failed to fetch events:', error)
      events.value = []
    } finally {
      isLoading.value = false
    }
  }
}, { immediate: true })
</script>