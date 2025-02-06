<template>
  <div>
    <div class="text-center mb-4 relative">
      <VueDatePicker
        v-model="date"
        :min-date="new Date()"
        :format="formatDate"
        :placeholder="'ライブ日程から探す'"
        :clearable="false"
        :enable-time-picker="false"
        auto-apply
        locale="ja"
        :input-class-name="'dp-custom-input'"
        @update:model-value="handleCalendarSelect"
        @clear="handleClear"
      >
      </VueDatePicker>
      <UButton 
        v-if="date"
        icon="i-heroicons-x-mark"
        color="gray"
        variant="ghost"
        class="absolute right-0 top-0 h-12 w-12"
        @click="handleClear"
      />
    </div>
  </div>
 </template>

<script setup lang="ts">
import { addDays, format } from 'date-fns'
import { ja } from 'date-fns/locale'
import VueDatePicker from '@vuepic/vue-datepicker'
import '@vuepic/vue-datepicker/dist/main.css'

const emit = defineEmits<{
  (e: 'select', date: string): void
  (e: 'clear'): void
}>()

const selectedDate = ref<string>('')
const date = ref<Date | null>(null)

const handleDateSelect = (date: string) => {
  selectedDate.value = date
  emit('select', date)
}

const handleCalendarSelect = (selectedDate: Date) => {
  if (selectedDate) {
    const dateStr = format(selectedDate, 'yyyy/MM/dd')
    handleDateSelect(dateStr)
  }
}

const handleClear = () => {
  selectedDate.value = ''
  date.value = null
  emit('clear')
}

const formatDate = (date: Date) => {
  return format(date, 'yyyy/MM/dd (E)', { locale: ja })
}
</script>


<style scoped>
.dp__main {
 width: 100%;
 margin: 0 auto;
}

:deep(.dp__input) {
 font-size: 0.9rem !important;
 height: 48px !important;
 padding: 0 38px !important;
 line-height: 48px !important;
 border: 1px solid rgb(209, 213, 219) !important; /* gray-200の色 */
 border-radius: 0.5rem !important;
}

:deep(.dp__input_icons) {
 font-size: 1rem !important;
}

:deep(.dp-custom-input) {
 padding-right: 3rem !important;
 font-size: 1rem !important;
}


:deep(.u-button:hover) {
 background-color: transparent;
}
</style>