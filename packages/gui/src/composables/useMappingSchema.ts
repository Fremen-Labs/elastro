import { ref, computed } from 'vue'

export interface FieldDef {
    name: string
    type: string
    ignore_above?: number
    properties?: FieldDef[]
}

export function useMappingSchema() {
    const fields = ref<FieldDef[]>([])
    const activePolicy = ref('strict')
    const templateTarget = ref('logs-*')

    const fieldTypes = [
        'text', 'keyword', 'long', 'integer', 'short', 'byte',
        'double', 'float', 'date', 'boolean', 'object', 'nested'
    ]

    const addRootField = (name: string, type: string) => {
        if (!name.trim() || !fieldTypes.includes(type)) return

        const newField: FieldDef = {
            name: name.trim(),
            type: type
        }

        if (newField.type === 'keyword') {
            newField.ignore_above = 256
        } else if (newField.type === 'object' || newField.type === 'nested') {
            newField.properties = []
        }

        fields.value.push(newField)
    }

    const removeField = (list: FieldDef[], index: number) => {
        list.splice(index, 1)
    }

    const addNestedField = (parent: FieldDef, name: string, type: string) => {
        if (!parent.properties) parent.properties = []
        if (!name.trim() || !fieldTypes.includes(type)) return

        const newField: FieldDef = {
            name: name.trim(),
            type: type
        }

        if (newField.type === 'keyword') {
            newField.ignore_above = 256
        } else if (newField.type === 'object' || newField.type === 'nested') {
            newField.properties = []
        }

        parent.properties.push(newField)
    }

    const generatedSchema = computed(() => {
        const buildProperties = (defs: FieldDef[]) => {
            const props: any = {}
            for (const f of defs) {
                props[f.name] = { type: f.type }
                if (f.ignore_above !== undefined) {
                    props[f.name].ignore_above = f.ignore_above
                }
                if ((f.type === 'object' || f.type === 'nested') && f.properties && f.properties.length > 0) {
                    props[f.name].properties = buildProperties(f.properties)
                }
            }
            return props
        }

        const mappingBody = {
            mappings: {
                dynamic: activePolicy.value,
                properties: buildProperties(fields.value)
            }
        }

        return JSON.stringify(mappingBody, null, 2)
    })

    return {
        fields,
        activePolicy,
        templateTarget,
        fieldTypes,
        addRootField,
        removeField,
        addNestedField,
        generatedSchema
    }
}
